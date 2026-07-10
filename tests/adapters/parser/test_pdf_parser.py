from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)

from adapters.parser import pdf_parser
from adapters.parser.pdf_parser import (
    PdfParser,
    _pdfplumber_is_meaningful_recovery,
    _pypdf_text_looks_corrupted,
)
from core.domain.exceptions import DocumentParseError

_CJK = "\u4e2d"
_CJK_EXT_A = "\u3da7"
_CORRUPT_CONTROL = "\x01"


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    def __init__(self, pages: list[str]) -> None:
        self.is_encrypted = False
        self.pages = [_FakePage(text) for text in pages]


def test_pypdf_corruption_predicate_detects_failure_shape() -> None:
    text = _text_with_counts(cjk=1, corrupt=150, ascii_count=5849, cjk_char=_CJK_EXT_A)

    assert _pypdf_text_looks_corrupted(text) is True


def test_pypdf_corruption_predicate_ignores_clean_english() -> None:
    assert _pypdf_text_looks_corrupted("a" * 6000) is False


def test_pypdf_corruption_predicate_ignores_high_cjk_ratio() -> None:
    text = _text_with_counts(cjk=330, corrupt=20, ascii_count=650)

    assert _pypdf_text_looks_corrupted(text) is False


def test_pypdf_corruption_predicate_ignores_short_text() -> None:
    text = _text_with_counts(cjk=0, corrupt=50, ascii_count=49)

    assert _pypdf_text_looks_corrupted(text) is False


def test_pypdf_corruption_predicate_ignores_low_corruption_ratio() -> None:
    text = _text_with_counts(cjk=0, corrupt=4, ascii_count=996)

    assert _pypdf_text_looks_corrupted(text) is False


def test_pypdf_corruption_predicate_detects_replacement_character_shape() -> None:
    text = "\ufffd" * 10 + "a" * 990

    assert _pypdf_text_looks_corrupted(text) is True


def test_pypdf_corruption_predicate_cjk_ratio_boundary() -> None:
    above_boundary = _text_with_counts(cjk=11, corrupt=10, ascii_count=979)
    below_boundary = _text_with_counts(cjk=9, corrupt=10, ascii_count=981)

    assert _pypdf_text_looks_corrupted(above_boundary) is False
    assert _pypdf_text_looks_corrupted(below_boundary) is True


def test_pdfplumber_recovery_guard_requires_meaningful_cjk_recovery() -> None:
    pypdf_text = _text_with_counts(cjk=1, corrupt=150, ascii_count=5849, cjk_char=_CJK_EXT_A)
    plumber_text = _CJK * 3772 + "a" * 5000

    assert _pdfplumber_is_meaningful_recovery(pypdf_text, plumber_text) is True


def test_pdf_parser_adopts_pdfplumber_recovery_and_rebuilds_locators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pdf_reader(
        monkeypatch,
        [_text_with_counts(cjk=1, corrupt=150, ascii_count=5849, cjk_char=_CJK_EXT_A)],
    )
    plumber_text = f"[S1]\n{_CJK * 3772}\nKt = 2"
    monkeypatch.setattr(pdf_parser, "_extract_with_pdfplumber", lambda _: (plumber_text, ["S1"]))

    parser = PdfParser(min_text_chars=0)
    parsed = parser.parse(_write_pdf_magic(tmp_path))

    assert parsed.raw_text == plumber_text
    assert parsed.locator_index.section_ids == ["S1"]
    assert parsed.locator_index.equation_ids == ["EQ-01"]
    assert parser.last_fallback_diagnostics["fallback_attempted"] is True
    assert parser.last_fallback_diagnostics["fallback_adopted"] is True
    assert parser.last_fallback_diagnostics["plumber_cjk_count"] == 3772


def test_pdf_parser_rejects_pdfplumber_text_with_incidental_cjk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pypdf_page = _text_with_counts(cjk=1, corrupt=150, ascii_count=5849, cjk_char=_CJK_EXT_A)
    _install_fake_pdf_reader(monkeypatch, [pypdf_page])
    plumber_text = f"[S1]\n{_CJK} clean but not enough recovery"
    monkeypatch.setattr(pdf_parser, "_extract_with_pdfplumber", lambda _: (plumber_text, ["S1"]))

    parser = PdfParser(min_text_chars=0)
    parsed = parser.parse(_write_pdf_magic(tmp_path))

    assert pypdf_page in parsed.raw_text
    assert plumber_text not in parsed.raw_text
    assert parser.last_fallback_diagnostics["fallback_failure_code"] == "pdfplumber_fallback_failed"
    assert parser.last_fallback_diagnostics["fallback_adopted"] is False


def test_pdf_parser_rejects_pdfplumber_text_when_corruption_ratio_does_not_drop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pypdf_page = _text_with_counts(cjk=1, corrupt=150, ascii_count=5849, cjk_char=_CJK_EXT_A)
    _install_fake_pdf_reader(monkeypatch, [pypdf_page])
    plumber_text = f"[S1]\n{_text_with_counts(cjk=100, corrupt=100, ascii_count=3134)}"
    monkeypatch.setattr(pdf_parser, "_extract_with_pdfplumber", lambda _: (plumber_text, ["S1"]))

    parser = PdfParser(min_text_chars=0)
    parsed = parser.parse(_write_pdf_magic(tmp_path))

    assert pypdf_page in parsed.raw_text
    assert plumber_text not in parsed.raw_text
    assert parser.last_fallback_diagnostics["fallback_adopted"] is False


def test_pdf_parser_fail_opens_when_pdfplumber_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pypdf_page = _text_with_counts(cjk=1, corrupt=150, ascii_count=5849, cjk_char=_CJK_EXT_A)
    _install_fake_pdf_reader(monkeypatch, [pypdf_page])

    def raise_pdfplumber_error(_: Path) -> Any:
        raise RuntimeError("pdfplumber unavailable")

    monkeypatch.setattr(pdf_parser, "_extract_with_pdfplumber", raise_pdfplumber_error)

    parser = PdfParser(min_text_chars=0)
    parsed = parser.parse(_write_pdf_magic(tmp_path))

    assert pypdf_page in parsed.raw_text
    assert parser.last_fallback_diagnostics["fallback_failure_code"] == "pdfplumber_fallback_failed"
    assert parser.last_fallback_diagnostics["fallback_adopted"] is False


def test_pdf_parser_does_not_call_pdfplumber_when_predicate_does_not_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pypdf_page = "a" * 6000
    _install_fake_pdf_reader(monkeypatch, [pypdf_page])

    def fail_if_called(_: Path) -> Any:
        raise AssertionError("pdfplumber should not be called")

    monkeypatch.setattr(pdf_parser, "_extract_with_pdfplumber", fail_if_called)

    parser = PdfParser(min_text_chars=0)
    parsed = parser.parse(_write_pdf_magic(tmp_path))

    assert pypdf_page in parsed.raw_text
    assert parser.last_fallback_diagnostics["fallback_attempted"] is False
    assert parser.last_fallback_diagnostics["fallback_adopted"] is False


def test_pdf_active_gate_allows_open_action_destination_array(tmp_path: Path) -> None:
    writer, page = _base_pdf_writer()
    writer._root_object[NameObject("/OpenAction")] = ArrayObject(
        [page.indirect_reference, NameObject("/Fit")]
    )

    parsed = PdfParser(min_text_chars=0).parse(_write_pdf(tmp_path, writer))

    assert parsed.page_count == 1


@pytest.mark.parametrize("destination_kind", ["direct_array", "indirect_array", "named"])
def test_pdf_active_gate_allows_open_action_goto_destinations(
    tmp_path: Path,
    destination_kind: str,
) -> None:
    writer, page = _base_pdf_writer()
    if destination_kind == "direct_array":
        destination: object = ArrayObject([page.indirect_reference, NameObject("/Fit")])
    elif destination_kind == "indirect_array":
        destination = writer._add_object(ArrayObject([page.indirect_reference, NameObject("/Fit")]))
    else:
        writer.add_named_destination("target-page", 0)
        destination = TextStringObject("target-page")
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {NameObject("/S"): NameObject("/GoTo"), NameObject("/D"): destination}
    )

    parsed = PdfParser(min_text_chars=0).parse(_write_pdf(tmp_path, writer))

    assert parsed.page_count == 1


def test_pdf_active_gate_allows_link_uri_annotation(tmp_path: Path) -> None:
    writer, page = _base_pdf_writer()
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): _rect(),
                NameObject("/A"): DictionaryObject(
                    {
                        NameObject("/S"): NameObject("/URI"),
                        NameObject("/URI"): TextStringObject("https://example.test/paper"),
                    }
                ),
            }
        ),
    )

    parsed = PdfParser(min_text_chars=0).parse(_write_pdf(tmp_path, writer))

    assert parsed.page_count == 1


def test_pdf_active_gate_allows_outline_goto_sibling_next(tmp_path: Path) -> None:
    writer, page = _base_pdf_writer()
    _add_outline_tree(writer, page, action_has_next=False)

    parsed = PdfParser(min_text_chars=0).parse(_write_pdf(tmp_path, writer))

    assert parsed.page_count == 1


@pytest.mark.parametrize(
    "builder",
    [
        pytest.param(lambda tmp_path: _pdf_with_open_action_next(tmp_path), id="goto-next-launch"),
        pytest.param(
            lambda tmp_path: _pdf_with_open_action_next_array(tmp_path), id="next-array-js"
        ),
        pytest.param(
            lambda tmp_path: _pdf_with_self_referential_action_next(tmp_path), id="next-cycle"
        ),
        pytest.param(lambda tmp_path: _pdf_with_open_action_uri(tmp_path), id="auto-uri"),
        pytest.param(lambda tmp_path: _pdf_with_page_additional_action(tmp_path), id="page-aa-uri"),
        pytest.param(
            lambda tmp_path: _pdf_with_annotation_additional_action(tmp_path), id="annot-aa"
        ),
        pytest.param(lambda tmp_path: _pdf_with_launch_annotation(tmp_path), id="launch-only"),
        pytest.param(lambda tmp_path: _pdf_with_open_action_type(tmp_path, "/GoToE"), id="gotoe"),
        pytest.param(
            lambda tmp_path: _pdf_with_open_action_type(tmp_path, "/RichMediaExecute"),
            id="richmediaexecute",
        ),
        pytest.param(lambda tmp_path: _pdf_with_document_javascript(tmp_path), id="names-js"),
        pytest.param(
            lambda tmp_path: _raw_pdf_with_escaped_javascript_name(tmp_path), id="escaped-js"
        ),
        pytest.param(lambda tmp_path: _pdf_with_xfa(tmp_path), id="xfa"),
        pytest.param(lambda tmp_path: _pdf_with_3d_on_instantiate(tmp_path), id="3d-script"),
        pytest.param(lambda tmp_path: _pdf_with_active_media(tmp_path), id="active-media"),
        pytest.param(
            lambda tmp_path: _pdf_with_embedded_files_name_tree(tmp_path), id="embedded-files"
        ),
        pytest.param(lambda tmp_path: _pdf_with_associated_file(tmp_path), id="af"),
        pytest.param(lambda tmp_path: _pdf_with_file_attachment(tmp_path), id="file-attachment"),
        pytest.param(lambda tmp_path: _pdf_with_pressteps(tmp_path), id="pressteps"),
        pytest.param(lambda tmp_path: _pdf_with_widget_uri_action(tmp_path), id="widget-uri"),
        pytest.param(
            lambda tmp_path: _pdf_with_outline_action_next(tmp_path), id="outline-action-next"
        ),
        pytest.param(
            lambda tmp_path: _pdf_with_open_action_type(tmp_path, "/Custom"), id="unknown-s"
        ),
        pytest.param(lambda tmp_path: _pdf_with_unresolvable_goto(tmp_path), id="bad-destination"),
        pytest.param(lambda tmp_path: _raw_pdf_with_bad_startxref(tmp_path), id="bad-startxref"),
    ],
)
def test_pdf_active_gate_rejects_unsafe_or_unverifiable_pdfs(
    tmp_path: Path,
    builder: Any,
) -> None:
    path = builder(tmp_path)

    with pytest.raises(DocumentParseError) as exc_info:
        PdfParser(min_text_chars=0).parse(path)

    assert exc_info.value.args == ("active_pdf_content_not_supported",)


def test_pdf_active_gate_rejects_budget_overrun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf_parser, "PDF_SECURITY_MAX_NODES", 0)
    writer, _ = _base_pdf_writer()

    with pytest.raises(DocumentParseError) as exc_info:
        PdfParser(min_text_chars=0).parse(_write_pdf(tmp_path, writer))

    assert exc_info.value.args == ("active_pdf_content_not_supported",)


def test_pdf_active_gate_ignores_large_harmless_object_graph(tmp_path: Path) -> None:
    writer, _ = _base_pdf_writer()
    writer._root_object[NameObject("/Harmless")] = ArrayObject(
        [DictionaryObject({NameObject("/N"): NumberObject(index)}) for index in range(6000)]
    )

    parsed = PdfParser(min_text_chars=0).parse(_write_pdf(tmp_path, writer))

    assert parsed.page_count == 1


@pytest.mark.parametrize(
    "builder",
    [
        pytest.param(lambda tmp_path: _pdf_with_document_javascript(tmp_path), id="js-name-tree"),
        pytest.param(lambda tmp_path: _pdf_with_xfa(tmp_path), id="xfa"),
        pytest.param(lambda tmp_path: _pdf_with_3d_on_instantiate(tmp_path), id="3d-script"),
        pytest.param(lambda tmp_path: _pdf_with_active_media(tmp_path), id="active-media"),
        pytest.param(
            lambda tmp_path: _pdf_with_embedded_files_name_tree(tmp_path), id="embedded-files"
        ),
        pytest.param(lambda tmp_path: _pdf_with_associated_file(tmp_path), id="af"),
        pytest.param(lambda tmp_path: _pdf_with_file_attachment(tmp_path), id="file-attachment"),
        pytest.param(lambda tmp_path: _pdf_with_annotation_filespec_ef(tmp_path), id="filespec-ef"),
    ],
)
def test_pdf_active_gate_targeted_non_action_detectors_reject_specified_entries(
    tmp_path: Path,
    builder: Any,
) -> None:
    with pytest.raises(DocumentParseError) as exc_info:
        PdfParser(min_text_chars=0).parse(builder(tmp_path))

    assert exc_info.value.args == ("active_pdf_content_not_supported",)


def _text_with_counts(
    *,
    cjk: int,
    corrupt: int,
    ascii_count: int,
    cjk_char: str = _CJK,
) -> str:
    return cjk_char * cjk + _CORRUPT_CONTROL * corrupt + "a" * ascii_count


def _install_fake_pdf_reader(monkeypatch: pytest.MonkeyPatch, pages: list[str]) -> None:
    monkeypatch.setattr(pdf_parser, "_reject_active_pdf_content", lambda _: None)

    def fake_pdf_reader(_: str, strict: bool = False) -> _FakeReader:
        assert strict is False
        return _FakeReader(pages)

    monkeypatch.setattr(pdf_parser, "PdfReader", fake_pdf_reader)


def _write_pdf_magic(tmp_path: Path) -> Path:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.7\n%%EOF")
    return path


def _base_pdf_writer() -> tuple[PdfWriter, Any]:
    writer = PdfWriter()
    page = writer.add_blank_page(width=72, height=72)
    return writer, page


def _write_pdf(tmp_path: Path, writer: PdfWriter, name: str = "paper.pdf") -> Path:
    path = tmp_path / name
    with path.open("wb") as stream:
        writer.write(stream)
    return path


def _rect() -> ArrayObject:
    return ArrayObject([NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)])


def _attach_annotation(writer: PdfWriter, page: Any, annotation: DictionaryObject) -> None:
    annotation_ref = writer._add_object(annotation)
    page[NameObject("/Annots")] = ArrayObject([annotation_ref])


def _safe_goto_action(page: Any) -> DictionaryObject:
    return DictionaryObject(
        {
            NameObject("/S"): NameObject("/GoTo"),
            NameObject("/D"): ArrayObject([page.indirect_reference, NameObject("/Fit")]),
        }
    )


def _add_outline_tree(writer: PdfWriter, page: Any, *, action_has_next: bool) -> None:
    outline_root = DictionaryObject({NameObject("/Type"): NameObject("/Outlines")})
    outline_root_ref = writer._add_object(outline_root)
    first_action = _safe_goto_action(page)
    if action_has_next:
        first_action[NameObject("/Next")] = DictionaryObject(
            {NameObject("/S"): NameObject("/Launch")}
        )

    first = DictionaryObject(
        {
            NameObject("/Title"): TextStringObject("First"),
            NameObject("/Parent"): outline_root_ref,
            NameObject("/A"): first_action,
        }
    )
    second = DictionaryObject(
        {
            NameObject("/Title"): TextStringObject("Second"),
            NameObject("/Parent"): outline_root_ref,
            NameObject("/A"): _safe_goto_action(page),
        }
    )
    first_ref = writer._add_object(first)
    second_ref = writer._add_object(second)
    first[NameObject("/Next")] = second_ref
    second[NameObject("/Prev")] = first_ref
    outline_root[NameObject("/First")] = first_ref
    outline_root[NameObject("/Last")] = second_ref
    outline_root[NameObject("/Count")] = NumberObject(2)
    writer._root_object[NameObject("/Outlines")] = outline_root_ref


def _pdf_with_open_action_next(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    action = _safe_goto_action(page)
    action[NameObject("/Next")] = DictionaryObject({NameObject("/S"): NameObject("/Launch")})
    writer._root_object[NameObject("/OpenAction")] = action
    return _write_pdf(tmp_path, writer)


def _pdf_with_open_action_next_array(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    action = _safe_goto_action(page)
    action[NameObject("/Next")] = ArrayObject(
        [
            _safe_goto_action(page),
            DictionaryObject(
                {
                    NameObject("/S"): NameObject("/JavaScript"),
                    NameObject("/JS"): TextStringObject("x"),
                }
            ),
        ]
    )
    writer._root_object[NameObject("/OpenAction")] = action
    return _write_pdf(tmp_path, writer)


def _pdf_with_self_referential_action_next(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    action = _safe_goto_action(page)
    action_ref = writer._add_object(action)
    action[NameObject("/Next")] = action_ref
    writer._root_object[NameObject("/OpenAction")] = action_ref
    return _write_pdf(tmp_path, writer)


def _pdf_with_open_action_uri(tmp_path: Path) -> Path:
    writer, _ = _base_pdf_writer()
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {
            NameObject("/S"): NameObject("/URI"),
            NameObject("/URI"): TextStringObject("https://example.test/open"),
        }
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_page_additional_action(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    page[NameObject("/AA")] = DictionaryObject(
        {
            NameObject("/O"): DictionaryObject(
                {
                    NameObject("/S"): NameObject("/URI"),
                    NameObject("/URI"): TextStringObject("https://example.test/open"),
                }
            )
        }
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_annotation_additional_action(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): _rect(),
                NameObject("/AA"): DictionaryObject(
                    {NameObject("/E"): DictionaryObject({NameObject("/S"): NameObject("/Launch")})}
                ),
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_launch_annotation(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): _rect(),
                NameObject("/A"): DictionaryObject({NameObject("/S"): NameObject("/Launch")}),
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_open_action_type(tmp_path: Path, subtype: str) -> Path:
    writer, _ = _base_pdf_writer()
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {NameObject("/S"): NameObject(subtype)}
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_document_javascript(tmp_path: Path) -> Path:
    writer, _ = _base_pdf_writer()
    writer.add_js("app.alert('blocked')")
    return _write_pdf(tmp_path, writer)


def _pdf_with_xfa(tmp_path: Path) -> Path:
    writer, _ = _base_pdf_writer()
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject(
        {NameObject("/XFA"): TextStringObject("xfa")}
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_3d_on_instantiate(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    stream = StreamObject()
    stream._data = b""
    stream[NameObject("/Type")] = NameObject("/3D")
    stream[NameObject("/Subtype")] = NameObject("/U3D")
    stream[NameObject("/OnInstantiate")] = TextStringObject("script")
    stream_ref = writer._add_object(stream)
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/3D"),
                NameObject("/Rect"): _rect(),
                NameObject("/3DD"): stream_ref,
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_active_media(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/RichMedia"),
                NameObject("/Rect"): _rect(),
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_embedded_files_name_tree(tmp_path: Path) -> Path:
    writer, _ = _base_pdf_writer()
    writer._root_object[NameObject("/Names")] = DictionaryObject(
        {
            NameObject("/EmbeddedFiles"): DictionaryObject(
                {
                    NameObject("/Names"): ArrayObject(
                        [TextStringObject("payload"), DictionaryObject()]
                    )
                }
            )
        }
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_associated_file(tmp_path: Path) -> Path:
    writer, _ = _base_pdf_writer()
    filespec = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Filespec"),
                NameObject("/F"): TextStringObject("payload.bin"),
                NameObject("/EF"): DictionaryObject(
                    {NameObject("/F"): ByteStringObject(b"payload")}
                ),
            }
        )
    )
    writer._root_object[NameObject("/AF")] = ArrayObject([filespec])
    return _write_pdf(tmp_path, writer)


def _pdf_with_file_attachment(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/FileAttachment"),
                NameObject("/Rect"): _rect(),
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_annotation_filespec_ef(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    filespec = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Filespec"),
                NameObject("/F"): TextStringObject("payload.bin"),
                NameObject("/EF"): DictionaryObject(
                    {NameObject("/F"): ByteStringObject(b"payload")}
                ),
            }
        )
    )
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Text"),
                NameObject("/Rect"): _rect(),
                NameObject("/FS"): filespec,
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_pressteps(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    page[NameObject("/PresSteps")] = DictionaryObject(
        {NameObject("/NA"): DictionaryObject({NameObject("/S"): NameObject("/Launch")})}
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_widget_uri_action(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    _attach_annotation(
        writer,
        page,
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/Rect"): _rect(),
                NameObject("/A"): DictionaryObject(
                    {
                        NameObject("/S"): NameObject("/URI"),
                        NameObject("/URI"): TextStringObject("https://example.test/widget"),
                    }
                ),
            }
        ),
    )
    return _write_pdf(tmp_path, writer)


def _pdf_with_outline_action_next(tmp_path: Path) -> Path:
    writer, page = _base_pdf_writer()
    _add_outline_tree(writer, page, action_has_next=True)
    return _write_pdf(tmp_path, writer)


def _pdf_with_unresolvable_goto(tmp_path: Path) -> Path:
    writer, _ = _base_pdf_writer()
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {
            NameObject("/S"): NameObject("/GoTo"),
            NameObject("/D"): ArrayObject([DictionaryObject(), NameObject("/Fit")]),
        }
    )
    return _write_pdf(tmp_path, writer)


def _raw_pdf_with_escaped_javascript_name(tmp_path: Path) -> Path:
    return _write_raw_pdf(
        tmp_path,
        [
            b"<< /Type /Catalog /Pages 2 0 R /Names << /Java#53cript << /Names [] >> >> >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>",
        ],
        name="escaped-js.pdf",
    )


def _raw_pdf_with_bad_startxref(tmp_path: Path) -> Path:
    return _write_raw_pdf(
        tmp_path,
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>",
        ],
        name="bad-xref.pdf",
        startxref_delta=17,
    )


def _write_raw_pdf(
    tmp_path: Path,
    objects: list[bytes],
    *,
    name: str,
    startxref_delta: int = 0,
) -> Path:
    body = b"%PDF-1.7\n"
    offsets = [0]
    for index, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{index} 0 obj\n".encode("ascii") + content + b"\nendobj\n"
    xref_offset = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        xref += f"{offset:010d} 00000 n \n".encode("ascii")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset + startxref_delta}\n%%EOF\n"
    ).encode("ascii")
    path = tmp_path / name
    path.write_bytes(body + xref + trailer)
    return path
