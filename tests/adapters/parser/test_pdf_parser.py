from pathlib import Path
from typing import Any

import pytest

from adapters.parser import pdf_parser
from adapters.parser.pdf_parser import (
    PdfParser,
    _pdfplumber_is_meaningful_recovery,
    _pypdf_text_looks_corrupted,
)

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


def _text_with_counts(
    *,
    cjk: int,
    corrupt: int,
    ascii_count: int,
    cjk_char: str = _CJK,
) -> str:
    return cjk_char * cjk + _CORRUPT_CONTROL * corrupt + "a" * ascii_count


def _install_fake_pdf_reader(monkeypatch: pytest.MonkeyPatch, pages: list[str]) -> None:
    def fake_pdf_reader(_: str, strict: bool = False) -> _FakeReader:
        assert strict is False
        return _FakeReader(pages)

    monkeypatch.setattr(pdf_parser, "PdfReader", fake_pdf_reader)


def _write_pdf_magic(tmp_path: Path) -> Path:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.7\n%%EOF")
    return path
