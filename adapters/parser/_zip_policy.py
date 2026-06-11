from typing import Literal

ALLOW_EXTS = sorted(
    {
        ".bmp",
        ".c",
        ".csv",
        ".fig",
        ".gif",
        ".h",
        ".jpeg",
        ".jpg",
        ".json",
        ".m",
        ".mat",
        ".md",
        ".mdl",
        ".mldatx",
        ".mlx",
        ".png",
        ".prj",
        ".sldd",
        ".slreqx",
        ".sltx",
        ".slx",
        ".ssc",
        ".svg",
        ".tif",
        ".tiff",
        ".txt",
        ".webp",
        ".xml",
        ".yaml",
        ".yml",
    }
)

SKIP_EXTS = sorted([".mexa64", ".mexmaci64", ".mexw64", ".pdf"])

_ORIGINAL_DENY_EXTS: frozenset[str] = frozenset(
    {
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".msi",
        ".dll",
        ".cpl",
        ".sys",
        ".drv",
        ".ocx",
        ".so",
        ".dylib",
        ".sh",
        ".bash",
        ".zsh",
        ".command",
        ".app",
        ".dmg",
        ".pkg",
        ".run",
        ".bin",
        ".elf",
        ".out",
        ".appimage",
        ".py",
        ".pyc",
        ".pyo",
        ".pyd",
        ".ps1",
        ".vbs",
        ".js",
        ".mex",
        ".mexw64",
        ".mexa64",
        ".mexmaci64",
        ".p",
        ".mlappinstall",
        ".mlpkginstall",
        ".ctf",
        ".lnk",
        ".url",
        ".scf",
        ".hta",
        ".wsf",
        ".wsh",
        ".jse",
        ".vbe",
        ".psm1",
        ".reg",
        ".inf",
        ".docm",
        ".xlsm",
        ".pptm",
        ".xlam",
        ".xlsb",
        ".class",
        ".jar",
        ".war",
        ".ear",
        ".wasm",
        ".mjs",
        ".cjs",
    }
)

DENY_EXTS = sorted(ext for ext in _ORIGINAL_DENY_EXTS if ext not in SKIP_EXTS)

assert set(ALLOW_EXTS).isdisjoint(SKIP_EXTS)
assert set(ALLOW_EXTS).isdisjoint(DENY_EXTS)
assert set(SKIP_EXTS).isdisjoint(DENY_EXTS)


def classify_extension(ext: str) -> Literal["allow", "skip", "deny", "other"]:
    """按扩展名返回 allow / skip / deny / other。"""
    if ext in SKIP_EXTS:
        return "skip"
    if ext in ALLOW_EXTS:
        return "allow"
    if ext in DENY_EXTS:
        return "deny"
    return "other"
