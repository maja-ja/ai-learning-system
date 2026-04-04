"""pytest fixtures — FastAPI TestClient + 環境初始化。"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _dev_defaults_env(monkeypatch):
    """確保測試環境接受預設密碼。"""
    monkeypatch.setenv("ALLOW_DEV_DEFAULTS", "1")


@pytest.fixture()
def client():
    """回傳與 backend.api:app 綁定的同步 TestClient。"""
    # 延遲 import，讓 monkeypatch 先生效
    from backend.api import app
    return TestClient(app)
