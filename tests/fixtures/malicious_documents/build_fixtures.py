"""Build paper upload security fixtures in a temporary directory."""

from __future__ import annotations

import zipfile
from pathlib import Path

from pypdf import PdfWriter


def build_all(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "encrypted_pdf": root / "encrypted.pdf",
        "javascript_pdf": root / "javascript.pdf",
        "giant_pdf": root / "giant.pdf",
        "macro_docx": root / "macro.docx",
        "zip_bomb_docx": root / "zip_bomb.docx",
        "corrupted_docx": root / "corrupted.docx",
    }
    _build_encrypted_pdf(fixtures["encrypted_pdf"])
    _build_javascript_pdf(fixtures["javascript_pdf"])
    fixtures["giant_pdf"].write_bytes(b"%PDF-" + (b"0" * 4096))
    _build_macro_docx(fixtures["macro_docx"])
    _build_zip_bomb_docx(fixtures["zip_bomb_docx"])
    fixtures["corrupted_docx"].write_bytes(b"PK\x03\x04not-a-real-zip")
    return fixtures


def _build_encrypted_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    with path.open("wb") as stream:
        writer.write(stream)


def _build_javascript_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_js("app.alert('blocked')")
    with path.open("wb") as stream:
        writer.write(stream)


def _build_macro_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types></Types>")
        package.writestr("word/document.xml", "<w:document></w:document>")
        package.writestr("word/vbaProject.bin", b"macro")


def _build_zip_bomb_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", "<Types></Types>")
        package.writestr("word/document.xml", "A" * 4096)
