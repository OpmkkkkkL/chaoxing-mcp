"""测试公共设施：FakeResponse + mock 会话。

patch_http patch 在 requests.Session.request（最底层），保证
ChaoxingSession.get/post 的 _guard 风控守卫真实执行。
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from cxmcp.config import Config
from cxmcp.session import ChaoxingSession


class FakeResponse:
    def __init__(self, status_code=200, text="", url="https://x.chaoxing.com/ok", headers=None):
        self.status_code = status_code
        self.text = text if isinstance(text, str) else text.decode("utf-8", "replace")
        self.url = url
        self.headers = headers or {}
        self.content = text if isinstance(text, bytes) else text.encode("utf-8")

    def json(self):
        return json.loads(self.text)


def make_cfg(tmp_path, role="student", automation=False) -> Config:
    return Config(
        role=role,
        cookie_file=tmp_path / f"{role}_cookies.json",
        enable_automation=automation,
    )


def patch_http(sess: ChaoxingSession, routes: dict[str, Any]):
    """routes: {"url_substr": FakeResponse | list[FakeResponse]}。

    传 list 表示按调用顺序弹出（耗尽后落到 404）；
    传单个 FakeResponse 表示该路由每次都返回同一响应。
    """
    consumable = {k: list(v) for k, v in routes.items() if isinstance(v, list)}
    static = {k: v for k, v in routes.items() if not isinstance(v, list)}
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, **kw):
        calls.append((method, url))
        # 长关键字优先，避免短关键字（如 i.chaoxing.com）误匹配长域名
        for key in sorted(consumable, key=len, reverse=True):
            items = consumable[key]
            if key in url and items:
                return items.pop(0)
        for key in sorted(static, key=len, reverse=True):
            if key in url:
                return static[key]
        return FakeResponse(status_code=404, text="not found", url=url)

    p = patch.object(sess.http, "request", side_effect=fake_request)
    return p, calls


@pytest.fixture
def cfg(tmp_path):
    return make_cfg(tmp_path)
