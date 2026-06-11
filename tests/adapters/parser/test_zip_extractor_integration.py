import io
import zipfile
from pathlib import Path

from adapters.parser.zip_extractor import safe_extract
from app.config import AppSettings


def _settings(upload_dir: Path) -> AppSettings:
    return AppSettings(deepseek_api_key="test", upload_dir=str(upload_dir))


def _zip_bytes(entries: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_zip_extractor_skips_non_consumable_files_and_extracts_allowed_files(
    tmp_path: Path,
) -> None:
    upload_root = tmp_path / "uploads"
    dest = upload_root / "project"
    dest.mkdir(parents=True)

    safe_extract(
        _zip_bytes(
            {
                "src/controller.c": "int controller(void) { return 1; }",
                "include/controller.h": "int controller(void);",
                "native/controller.mexw64": b"MZ fake binary",
                "docs/paper.pdf": b"%PDF-1.7 fake",
                "model/controller.m": "disp('ok');",
                "model/controller.slx": b"fake slx bytes",
            }
        ),
        dest,
        _settings(upload_root),
    )

    assert (dest / "src" / "controller.c").read_text(encoding="utf-8")
    assert (dest / "include" / "controller.h").read_text(encoding="utf-8")
    assert (dest / "model" / "controller.m").read_text(encoding="utf-8")
    assert (dest / "model" / "controller.slx").read_bytes()
    assert not (dest / "native" / "controller.mexw64").exists()
    assert not (dest / "docs" / "paper.pdf").exists()
