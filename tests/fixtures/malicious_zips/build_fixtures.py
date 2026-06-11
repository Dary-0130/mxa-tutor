import os
import stat
import sys
import zipfile
from pathlib import Path


def build_all(out_dir: Path) -> None:
    """构造 7 个风险族 fixture 到 out_dir。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    build_zip_bomb_ratio(out_dir)
    build_zip_slip_paths(out_dir)
    build_symlink_chain(out_dir)
    build_duplicate_collision(out_dir)
    build_forbidden_type(out_dir)
    build_encrypted_or_bad_method(out_dir)
    build_total_uncompressed_exceeds_cap(out_dir)


def build_zip_bomb_ratio(out_dir: Path) -> None:
    payload = b"0" * (2 * 1024 * 1024)
    with zipfile.ZipFile(out_dir / "zip_bomb_ratio.zip", "w") as zf:
        zf.writestr("model.m", payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_zip_slip_paths(out_dir: Path) -> None:
    with zipfile.ZipFile(out_dir / "zip_slip_paths.zip", "w") as zf:
        zf.writestr("../escape.m", "disp('escape');")
        zf.writestr("safe/model.m", "disp('safe');")


def build_symlink_chain(out_dir: Path) -> None:
    with zipfile.ZipFile(out_dir / "symlink_chain.zip", "w") as zf:
        link = zipfile.ZipInfo("linkdir")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, "/tmp/outside-target")
        zf.writestr("linkdir/payload.m", "disp('should not be written');")


def build_duplicate_collision(out_dir: Path) -> None:
    with zipfile.ZipFile(out_dir / "duplicate_collision.zip", "w") as zf:
        zf.writestr("dup/a.m", "disp(1);")
        zf.writestr("dup/a.m", "disp(2);")
        zf.writestr("unicode/e\u0301.m", "disp(1);")
        zf.writestr("unicode/é.m", "disp(2);")
        zf.writestr("case/A.m", "disp(1);")
        zf.writestr("case/a.m", "disp(2);")


def build_forbidden_type(out_dir: Path) -> None:
    with zipfile.ZipFile(out_dir / "forbidden_type.zip", "w") as zf:
        zf.writestr("model.m", "disp('ok');")
        zf.writestr("native/evil.exe", b"MZ fake binary")


def build_encrypted_or_bad_method(out_dir: Path) -> None:
    with zipfile.ZipFile(out_dir / "encrypted_or_bad_method.zip", "w") as zf:
        zf.writestr(
            "bad_method/model.m",
            "disp('bzip2');",
            compress_type=zipfile.ZIP_BZIP2,
        )


def build_total_uncompressed_exceeds_cap(out_dir: Path) -> None:
    chunk = os.urandom(64 * 1024)
    with zipfile.ZipFile(out_dir / "total_uncompressed_exceeds_cap.zip", "w") as zf:
        for index in range(24):
            zf.writestr(
                f"data/part_{index:03d}.dat",
                chunk,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=1,
            )


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./_built_fixtures")
    build_all(output)
