from __future__ import annotations

from deepwiki.output.json_output import JSONFormatter


def test_mask_value_for_secret_like_fields() -> None:
    formatter = JSONFormatter()

    assert formatter._mask_value("api_key", "abcdefgh12345678") == "abcd****5678"
    assert formatter._mask_value("token", "short") == "****"
    assert formatter._mask_value("provider", "openai") == "openai"
