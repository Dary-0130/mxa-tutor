"""PDF parser adapter backed by pypdf."""

from __future__ import annotations

import importlib
import re
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    TextStringObject,
)

from core.domain.exceptions import DocumentParseError
from core.interfaces.document_parser import (
    DocumentParser,
    ParsedDocument,
    ParsedLocatorIndex,
    compute_file_hash,
)

PDF_MAGIC = b"%PDF-"
DEFAULT_MAX_PDF_BYTES = 50 * 1024 * 1024
DEFAULT_MIN_TEXT_CHARS = 100
FALLBACK_MIN_CHARS = 100
FALLBACK_MAX_PYPDF_CJK_RATIO = 0.01
FALLBACK_CORRUPTION_RATIO = 0.005
FALLBACK_MIN_RECOVERY_CJK = 50
_ALLOWED_CONTROL_WHITESPACE = "\t\n\r\f\v"
_PDFPLUMBER_FALLBACK_FAILED = "pdfplumber_fallback_failed"
_EQUATION_RE = re.compile(r"(^|\s)[A-Za-z][A-Za-z0-9_]*(\s*=|\s*\()")
PDF_SECURITY_MAX_NODES = 10000
PDF_SECURITY_MAX_DEPTH = 64
PDF_SECURITY_MAX_ACTIONS = 10000
PDF_SECURITY_MAX_OUTLINE_ITEMS = 10000
PDF_SECURITY_MAX_FORM_FIELDS = 10000
PDF_SECURITY_MAX_SCAN_SECONDS = 10.0

_ACTIVE_MEDIA_SUBTYPES = {"/RichMedia", "/Screen", "/Movie", "/Sound"}
_KNOWN_UNSUPPORTED_ACTION_REASONS = {
    "/JavaScript": "pdf_action_javascript_unsupported",
    "/JS": "pdf_action_javascript_unsupported",
    "/Launch": "pdf_action_launch_unsupported",
    "/GoToR": "pdf_action_remote_goto_unsupported",
    "/GoToE": "pdf_action_embedded_goto_unsupported",
    "/SubmitForm": "pdf_action_form_submit_unsupported",
    "/ImportData": "pdf_action_import_data_unsupported",
    "/RichMediaExecute": "pdf_action_rich_media_execute_unsupported",
}

PdfFallbackDiagnostics = dict[str, bool | int | float | str | None]
PdfTextExtraction = tuple[str, list[str]]


class PdfParser(DocumentParser):
    """Extract text and locator hints from a PDF without executing embedded content."""

    def __init__(
        self,
        max_file_bytes: int = DEFAULT_MAX_PDF_BYTES,
        min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
    ) -> None:
        self._max_file_bytes = max_file_bytes
        self._min_text_chars = min_text_chars
        self._last_fallback_diagnostics: PdfFallbackDiagnostics = {}

    @property
    def last_fallback_diagnostics(self) -> PdfFallbackDiagnostics:
        return dict(self._last_fallback_diagnostics)

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf" and _read_prefix(file_path, 5) == PDF_MAGIC

    def parse(self, file_path: Path, timeout_seconds: float = 30.0) -> ParsedDocument:
        _ = timeout_seconds
        self._last_fallback_diagnostics = {}
        if not self.supports(file_path):
            raise DocumentParseError("unsupported_pdf_format") from None
        if file_path.stat().st_size > self._max_file_bytes:
            raise DocumentParseError("pdf_too_large") from None
        _reject_active_pdf_content(file_path)

        try:
            reader = PdfReader(str(file_path), strict=False)
        except (OSError, PdfReadError, ValueError):
            raise DocumentParseError("pdf_parse_failed") from None

        if reader.is_encrypted:
            raise DocumentParseError("encrypted_pdf_not_supported") from None

        page_texts: list[str] = []
        section_ids: list[str] = []
        try:
            for index, page in enumerate(reader.pages, start=1):
                section_id = f"S{index}"
                section_ids.append(section_id)
                text = (page.extract_text() or "").strip()
                if text:
                    page_texts.append(f"[{section_id}]\n{text}")
        except (PdfReadError, ValueError, KeyError):
            raise DocumentParseError("pdf_parse_failed") from None

        raw_text = "\n\n".join(page_texts).strip()
        raw_text, section_ids, self._last_fallback_diagnostics = _maybe_apply_pdfplumber_fallback(
            file_path,
            raw_text,
            section_ids,
        )
        if len(raw_text) < self._min_text_chars:
            raise DocumentParseError("document_text_too_short") from None

        return ParsedDocument(
            raw_text=raw_text,
            page_count=len(reader.pages),
            figure_placeholders=[],
            table_placeholders=[],
            locator_index=ParsedLocatorIndex(
                section_ids=section_ids,
                equation_ids=_extract_equation_ids(raw_text),
                figure_ids=[],
            ),
            file_hash=compute_file_hash(file_path),
            extracted_at=datetime.now(UTC),
        )


def _read_prefix(file_path: Path, size: int) -> bytes:
    try:
        with file_path.open("rb") as stream:
            return stream.read(size)
    except OSError:
        return b""


def _reject_active_pdf_content(file_path: Path) -> None:
    try:
        reader = PdfReader(str(file_path), strict=True)
    except (OSError, PdfReadError, ValueError, KeyError):
        raise DocumentParseError("active_pdf_content_not_supported") from None

    if reader.is_encrypted:
        return

    try:
        _PdfActiveContentScanner(reader).scan()
    except _PdfActiveContentRejected:
        raise DocumentParseError("active_pdf_content_not_supported") from None


class _PdfActiveContentRejected(Exception):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class _PdfActiveContentScanner:
    def __init__(self, reader: PdfReader) -> None:
        self._reader = reader
        self._started_at = time.monotonic()
        self._scan_nodes = 0
        self._action_roots = 0
        self._outline_items = 0
        self._form_fields = 0
        self._visited_outlines: set[tuple[object, ...]] = set()
        self._visited_fields: set[tuple[object, ...]] = set()
        self._page_ref_ids = self._build_page_ref_ids()

    def scan(self) -> None:
        catalog = self._as_dictionary(self._reader.root_object)

        self._scan_non_action_active_entries(catalog)
        self._scan_catalog_action_roots(catalog)
        self._scan_acroform(catalog)
        self._scan_outlines(catalog)
        self._scan_pages()

    def _scan_non_action_active_entries(self, catalog: DictionaryObject) -> None:
        self._count_security_node(depth=0)
        if "/Names" in catalog:
            self._scan_catalog_names(catalog["/Names"], depth=1)

    def _scan_catalog_names(self, names: object, depth: int) -> None:
        self._count_security_node(depth=depth)
        names = self._as_dictionary(names)
        if "/JavaScript" in names:
            self._reject("pdf_document_javascript_name_tree")
        if "/EmbeddedFiles" in names:
            self._reject("pdf_embedded_file_present")

    def _scan_catalog_action_roots(self, catalog: DictionaryObject) -> None:
        if "/OpenAction" in catalog:
            open_action = self._resolve(catalog["/OpenAction"])
            if isinstance(open_action, ArrayObject):
                self._validate_destination(open_action)
            elif isinstance(open_action, DictionaryObject):
                self._validate_action(open_action, context="document_open")
            else:
                self._reject("pdf_open_action_unsupported")

        if "/AA" in catalog:
            self._reject("pdf_additional_actions_unsupported")

        if "/AF" in catalog:
            self._reject("pdf_embedded_file_present")

    def _scan_acroform(self, catalog: DictionaryObject) -> None:
        if "/AcroForm" not in catalog:
            return

        acroform = self._as_dictionary(catalog["/AcroForm"])
        if "/XFA" in acroform:
            self._reject("pdf_xfa_present")
        if "/Fields" in acroform:
            fields = self._as_array(acroform["/Fields"])
            for field in fields:
                self._scan_form_field(field, depth=0)

    def _scan_form_field(self, field: object, depth: int) -> None:
        self._guard_budget(depth=depth)
        field = self._resolve(field)
        key = self._visit_key(field)
        if key in self._visited_fields:
            return
        self._visited_fields.add(key)
        self._form_fields += 1
        if self._form_fields > PDF_SECURITY_MAX_FORM_FIELDS:
            self._reject("pdf_structure_unverifiable")
        if not isinstance(field, DictionaryObject):
            self._reject("pdf_structure_unverifiable")

        if "/AA" in field:
            self._reject("pdf_additional_actions_unsupported")
        if self._name_value(field, "/Subtype") == "/Widget" and "/A" in field:
            self._scan_annotation(field)
        if "/Kids" in field:
            kids = self._as_array(field["/Kids"])
            for kid in kids:
                self._scan_form_field(kid, depth=depth + 1)

    def _scan_outlines(self, catalog: DictionaryObject) -> None:
        if "/Outlines" not in catalog:
            return

        outlines = self._as_dictionary(catalog["/Outlines"])
        if "/First" in outlines:
            self._scan_outline_item(outlines["/First"], depth=0)

    def _scan_outline_item(self, item: object, depth: int) -> None:
        self._guard_budget(depth=depth)
        item = self._resolve(item)
        key = self._visit_key(item)
        if key in self._visited_outlines:
            return
        self._visited_outlines.add(key)
        self._outline_items += 1
        if self._outline_items > PDF_SECURITY_MAX_OUTLINE_ITEMS:
            self._reject("pdf_structure_unverifiable")
        if not isinstance(item, DictionaryObject):
            self._reject("pdf_structure_unverifiable")

        if "/A" in item:
            self._validate_action(item["/A"], context="outline")
        if "/First" in item:
            self._scan_outline_item(item["/First"], depth=depth + 1)
        if "/Next" in item:
            self._scan_outline_item(item["/Next"], depth=depth)

    def _scan_pages(self) -> None:
        try:
            pages = list(self._reader.pages)
        except (PdfReadError, ValueError, KeyError, TypeError, RecursionError):
            self._reject("pdf_structure_unverifiable")

        for page in pages:
            page_obj = self._as_dictionary(page)
            if "/AA" in page_obj:
                self._reject("pdf_additional_actions_unsupported")
            if "/PresSteps" in page_obj:
                self._reject("pdf_subpage_navigation_unsupported")
            if "/AF" in page_obj:
                self._reject("pdf_embedded_file_present")
            if "/Annots" in page_obj:
                annots = self._as_array(page_obj["/Annots"])
                for annotation in annots:
                    self._scan_annotation(annotation)

    def _scan_annotation(self, annotation: object) -> None:
        annotation = self._as_dictionary(annotation)
        subtype = self._name_value(annotation, "/Subtype")
        if subtype in _ACTIVE_MEDIA_SUBTYPES:
            self._reject("pdf_active_media_present")
        if subtype == "/3D":
            self._scan_3d_annotation(annotation)
        if subtype == "/FileAttachment":
            self._reject("pdf_embedded_file_present")
        if "/AF" in annotation:
            self._reject("pdf_embedded_file_present")
        if "/FS" in annotation:
            self._scan_file_spec(annotation["/FS"])
        if "/AA" in annotation:
            self._reject("pdf_additional_actions_unsupported")
        if "/A" in annotation:
            if subtype != "/Link":
                self._reject("pdf_annotation_action_unsupported")
            self._validate_action(annotation["/A"], context="annotation_click")

    def _scan_3d_annotation(self, annotation: DictionaryObject) -> None:
        if "/OnInstantiate" in annotation:
            self._reject("pdf_3d_script_present")
        if "/3DD" not in annotation:
            return
        self._count_security_node(depth=1)
        three_d_data = self._as_dictionary(annotation["/3DD"])
        if "/OnInstantiate" in three_d_data:
            self._reject("pdf_3d_script_present")

    def _scan_file_spec(self, file_spec: object) -> None:
        self._count_security_node(depth=1)
        file_spec = self._resolve(file_spec)
        if not isinstance(file_spec, DictionaryObject):
            return
        if "/EF" in file_spec:
            self._reject("pdf_embedded_file_present")

    def _validate_action(self, action: object, *, context: str) -> None:
        self._action_roots += 1
        if self._action_roots > PDF_SECURITY_MAX_ACTIONS:
            self._reject("pdf_structure_unverifiable")

        action = self._as_dictionary(action)
        if "/Next" in action:
            self._reject("pdf_action_next_unsupported")
        if "/S" not in action:
            self._reject("pdf_action_type_missing")

        subtype = self._resolve(action["/S"])
        if not isinstance(subtype, NameObject):
            self._reject("pdf_action_type_invalid")
        subtype_text = str(subtype)

        if subtype_text == "/GoTo":
            if context not in {"document_open", "annotation_click", "outline"}:
                self._reject("pdf_action_type_unsupported")
            if "/D" not in action:
                self._reject("pdf_internal_destination_unresolvable")
            self._validate_destination(action["/D"])
            return

        if subtype_text == "/URI":
            if context != "annotation_click":
                self._reject("pdf_action_uri_auto_unsupported")
            if "/URI" not in action:
                self._reject("pdf_uri_missing")
            uri = self._resolve(action["/URI"])
            if not isinstance(uri, TextStringObject | ByteStringObject):
                self._reject("pdf_uri_invalid")
            return

        if subtype_text in _KNOWN_UNSUPPORTED_ACTION_REASONS:
            self._reject(_KNOWN_UNSUPPORTED_ACTION_REASONS[subtype_text])
        self._reject("pdf_action_type_unsupported")

    def _validate_destination(self, destination: object) -> None:
        destination = self._resolve(destination)
        if isinstance(destination, ArrayObject):
            self._validate_destination_array(destination)
            return
        if isinstance(destination, NameObject | TextStringObject | ByteStringObject):
            self._validate_named_destination(destination)
            return
        self._reject("pdf_internal_destination_unresolvable")

    def _validate_destination_array(self, destination: ArrayObject) -> None:
        if len(destination) == 0:
            self._reject("pdf_internal_destination_unresolvable")

        page_ref = destination[0]
        if isinstance(page_ref, IndirectObject):
            try:
                page_obj = page_ref.get_object()
            except (PdfReadError, ValueError, KeyError, TypeError, RecursionError):
                self._reject("pdf_internal_destination_unresolvable")
            if not isinstance(page_obj, DictionaryObject):
                self._reject("pdf_internal_destination_unresolvable")
            if self._name_value(page_obj, "/Type") != "/Page":
                self._reject("pdf_internal_destination_unresolvable")
            if self._indirect_id(page_ref) in self._page_ref_ids:
                return
            self._reject("pdf_internal_destination_unresolvable")

        if isinstance(page_ref, DictionaryObject):
            ref_id = self._indirect_id_from_object(page_ref)
            if ref_id is not None and ref_id in self._page_ref_ids:
                return
        self._reject("pdf_internal_destination_unresolvable")

    def _validate_named_destination(
        self,
        destination: NameObject | TextStringObject | ByteStringObject,
    ) -> None:
        try:
            named_destinations = self._reader.named_destinations
        except (PdfReadError, ValueError, KeyError, TypeError, RecursionError):
            self._reject("pdf_internal_destination_unresolvable")

        wanted_names = self._destination_name_candidates(destination)
        for name, resolved_destination in named_destinations.items():
            if str(name) not in wanted_names:
                continue
            try:
                page_number = self._reader.get_destination_page_number(resolved_destination)
            except (PdfReadError, ValueError, KeyError, TypeError, RecursionError):
                self._reject("pdf_internal_destination_unresolvable")
            if page_number is not None and 0 <= page_number < len(self._reader.pages):
                return
            self._reject("pdf_internal_destination_unresolvable")

        self._reject("pdf_internal_destination_unresolvable")

    def _destination_name_candidates(
        self,
        destination: NameObject | TextStringObject | ByteStringObject,
    ) -> set[str]:
        if isinstance(destination, ByteStringObject):
            try:
                text = bytes(destination).decode("utf-8")
            except UnicodeDecodeError:
                self._reject("pdf_internal_destination_unresolvable")
        else:
            text = str(destination)

        candidates = {text}
        if isinstance(destination, NameObject) and text.startswith("/"):
            candidates.add(text[1:])
        return candidates

    def _build_page_ref_ids(self) -> set[tuple[int, int]]:
        ref_ids: set[tuple[int, int]] = set()
        try:
            pages = list(self._reader.pages)
        except (PdfReadError, ValueError, KeyError, TypeError, RecursionError):
            self._reject("pdf_structure_unverifiable")

        for page in pages:
            ref_id = self._indirect_id_from_object(page)
            if ref_id is not None:
                ref_ids.add(ref_id)
        return ref_ids

    def _name_value(self, obj: DictionaryObject, key: str) -> str | None:
        if key not in obj:
            return None
        value = self._resolve(obj[key])
        if isinstance(value, NameObject):
            return str(value)
        return None

    def _as_dictionary(self, obj: object) -> DictionaryObject:
        obj = self._resolve(obj)
        if not isinstance(obj, DictionaryObject):
            self._reject("pdf_structure_unverifiable")
        return obj

    def _as_array(self, obj: object) -> ArrayObject:
        obj = self._resolve(obj)
        if not isinstance(obj, ArrayObject):
            self._reject("pdf_structure_unverifiable")
        return obj

    def _resolve(self, obj: object) -> object:
        if isinstance(obj, IndirectObject):
            try:
                return obj.get_object()
            except (PdfReadError, ValueError, KeyError, TypeError, RecursionError):
                self._reject("pdf_structure_unverifiable")
        return obj

    def _visit_key(self, obj: object) -> tuple[object, ...]:
        if isinstance(obj, IndirectObject):
            return ("ref", obj.idnum, obj.generation)
        ref_id = self._indirect_id_from_object(obj)
        if ref_id is not None:
            return ("ref", ref_id[0], ref_id[1])
        return ("mem", id(obj))

    def _indirect_id_from_object(self, obj: object) -> tuple[int, int] | None:
        ref = getattr(obj, "indirect_reference", None)
        if isinstance(ref, IndirectObject):
            return self._indirect_id(ref)
        return None

    def _indirect_id(self, ref: IndirectObject) -> tuple[int, int]:
        return (int(ref.idnum), int(ref.generation))

    def _count_security_node(self, *, depth: int) -> None:
        self._guard_budget(depth=depth)
        self._scan_nodes += 1
        if self._scan_nodes > PDF_SECURITY_MAX_NODES:
            self._reject("pdf_structure_unverifiable")

    def _guard_budget(self, *, depth: int) -> None:
        if depth > PDF_SECURITY_MAX_DEPTH:
            self._reject("pdf_structure_unverifiable")
        if time.monotonic() - self._started_at > PDF_SECURITY_MAX_SCAN_SECONDS:
            self._reject("pdf_structure_unverifiable")

    def _reject(self, reason_code: str) -> NoReturn:
        raise _PdfActiveContentRejected(reason_code)


def _maybe_apply_pdfplumber_fallback(
    file_path: Path,
    pypdf_text: str,
    pypdf_section_ids: list[str],
) -> tuple[str, list[str], PdfFallbackDiagnostics]:
    diagnostics = _initial_fallback_diagnostics(pypdf_text)
    if not _pypdf_text_looks_corrupted(pypdf_text):
        return pypdf_text, pypdf_section_ids, diagnostics

    diagnostics["fallback_attempted"] = True
    try:
        plumber_extraction = _extract_with_pdfplumber(file_path)
    except Exception:
        diagnostics["fallback_failure_code"] = _PDFPLUMBER_FALLBACK_FAILED
        return pypdf_text, pypdf_section_ids, diagnostics

    if plumber_extraction is None:
        diagnostics["fallback_failure_code"] = _PDFPLUMBER_FALLBACK_FAILED
        return pypdf_text, pypdf_section_ids, diagnostics

    plumber_text, plumber_section_ids = plumber_extraction
    diagnostics["plumber_cjk_count"] = _cjk_count(plumber_text)
    diagnostics["plumber_corruption_ratio"] = _corruption_ratio(plumber_text)
    if _pdfplumber_is_meaningful_recovery(pypdf_text, plumber_text):
        diagnostics["fallback_adopted"] = True
        return plumber_text, plumber_section_ids, diagnostics

    diagnostics["fallback_failure_code"] = _PDFPLUMBER_FALLBACK_FAILED
    return pypdf_text, pypdf_section_ids, diagnostics


def _initial_fallback_diagnostics(pypdf_text: str) -> PdfFallbackDiagnostics:
    return {
        "pypdf_chars": len(pypdf_text),
        "pypdf_cjk_count": _cjk_count(pypdf_text),
        "pypdf_corruption_ratio": _corruption_ratio(pypdf_text),
        "fallback_attempted": False,
        "fallback_adopted": False,
        "plumber_cjk_count": 0,
        "plumber_corruption_ratio": 0.0,
        "fallback_failure_code": None,
    }


def _extract_with_pdfplumber(file_path: Path) -> PdfTextExtraction | None:
    pdfplumber = importlib.import_module("pdfplumber")
    pdfplumber_open = pdfplumber.open
    page_texts: list[str] = []
    section_ids: list[str] = []

    with pdfplumber_open(str(file_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            section_id = f"S{index}"
            section_ids.append(section_id)
            text = (page.extract_text() or "").strip()
            if text:
                page_texts.append(f"[{section_id}]\n{text}")

    return "\n\n".join(page_texts).strip(), section_ids


def _pypdf_text_looks_corrupted(text: str) -> bool:
    nonws = _non_whitespace_count(text)
    cjk_ratio = _cjk_count(text) / max(1, nonws)
    return (
        len(text.strip()) >= FALLBACK_MIN_CHARS
        and cjk_ratio <= FALLBACK_MAX_PYPDF_CJK_RATIO
        and _corruption_ratio(text) >= FALLBACK_CORRUPTION_RATIO
    )


def _pdfplumber_is_meaningful_recovery(pypdf_text: str, plumber_text: str) -> bool:
    return (
        len(plumber_text.strip()) >= FALLBACK_MIN_CHARS
        and _cjk_count(plumber_text) >= FALLBACK_MIN_RECOVERY_CJK
        and _cjk_count(plumber_text) > _cjk_count(pypdf_text)
        and _corruption_ratio(plumber_text) < _corruption_ratio(pypdf_text)
    )


def _corruption_ratio(text: str) -> float:
    corrupt = sum(1 for ch in text if _is_corrupt_pdf_text_marker(ch))
    return corrupt / max(1, _non_whitespace_count(text))


def _non_whitespace_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _is_corrupt_pdf_text_marker(ch: str) -> bool:
    return (
        unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROL_WHITESPACE
    ) or ch == "\ufffd"


def _cjk_count(text: str) -> int:
    return sum(1 for ch in text if _is_cjk(ch))


def _is_cjk(ch: str) -> bool:
    codepoint = ord(ch)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2EBEF
        or 0x30000 <= codepoint <= 0x323AF
    )


def _extract_equation_ids(raw_text: str) -> list[str]:
    return [f"EQ-{index:02d}" for index, line in enumerate(_equation_lines(raw_text), start=1)]


def _equation_lines(raw_text: str) -> list[str]:
    return [line for line in raw_text.splitlines() if _EQUATION_RE.search(line)]
