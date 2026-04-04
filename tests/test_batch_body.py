"""BatchDecodeBody 請求體驗證。"""
import pytest
from pydantic import ValidationError

# 使用 api.py 裡定義的 model
from backend.api import BatchDecodeBody


def test_valid_batch():
    body = BatchDecodeBody(
        words=["熵增定律", "賽局理論"],
        primary_category="物理科學",
    )
    assert len(body.words) == 2
    assert body.force_refresh is False
    assert body.delay_sec == 0.5


def test_delay_range():
    with pytest.raises(ValidationError):
        BatchDecodeBody(
            words=["test"],
            primary_category="X",
            delay_sec=10,  # max is 3
        )


def test_empty_words_allowed_by_pydantic():
    body = BatchDecodeBody(words=[], primary_category="X")
    assert body.words == []
