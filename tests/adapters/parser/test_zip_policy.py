import pytest

import adapters.parser._zip_policy as zip_policy
from adapters.parser._zip_policy import ALLOW_EXTS, DENY_EXTS, SKIP_EXTS, classify_extension


def test_c_h_in_allow_exts() -> None:
    assert ".c" in ALLOW_EXTS
    assert ".h" in ALLOW_EXTS


def test_mexw64_not_in_deny_exts() -> None:
    assert ".mexw64" not in DENY_EXTS


def test_mexw64_in_skip_exts() -> None:
    assert ".mexw64" in SKIP_EXTS


def test_pdf_in_skip_exts() -> None:
    assert ".pdf" in SKIP_EXTS


def test_classify_extension_returns_skip_for_mexw64() -> None:
    assert classify_extension(".mexw64") == "skip"


def test_classify_extension_returns_allow_for_c() -> None:
    assert classify_extension(".c") == "allow"


def test_zip_policy_sets_are_disjoint() -> None:
    assert set(ALLOW_EXTS).isdisjoint(SKIP_EXTS)
    assert set(ALLOW_EXTS).isdisjoint(DENY_EXTS)
    assert set(SKIP_EXTS).isdisjoint(DENY_EXTS)


def test_skip_exts_are_not_denied() -> None:
    assert not set(SKIP_EXTS) & set(DENY_EXTS)


def test_classify_extension_order_skip_before_allow_before_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ext = ".overlap"
    monkeypatch.setattr(zip_policy, "SKIP_EXTS", [ext])
    monkeypatch.setattr(zip_policy, "ALLOW_EXTS", [ext])
    monkeypatch.setattr(zip_policy, "DENY_EXTS", [ext])
    assert zip_policy.classify_extension(ext) == "skip"

    monkeypatch.setattr(zip_policy, "SKIP_EXTS", [])
    assert zip_policy.classify_extension(ext) == "allow"

    monkeypatch.setattr(zip_policy, "ALLOW_EXTS", [])
    assert zip_policy.classify_extension(ext) == "deny"
