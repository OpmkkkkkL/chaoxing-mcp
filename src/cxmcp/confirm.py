"""两阶段确认门：高影响操作（发布/提交/批改/删除/上传）必须先拿令牌。

设计要点（借鉴 chaoxing-agent）：
- 令牌 = 一次性 + 绑定 (action, params) 的 SHA-256 指纹，参数变化即失效；
- TTL 5 分钟；
- consume 成功即删除，防重放。
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

from .exceptions import ConfirmationRequired, ConfirmationRejected

TTL_SECONDS = 300


class ConfirmationStore:
    def __init__(self) -> None:
        # fingerprint -> {"token": str, "expires": float, "action": str}
        self._items: dict[str, dict[str, Any]] = {}

    @staticmethod
    def fingerprint(action: str, params: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"action": action, "params": params},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def issue(self, action: str, params: dict[str, Any], impact: str) -> str:
        self._sweep()
        fp = self.fingerprint(action, params)
        token = secrets.token_urlsafe(16)
        self._items[fp] = {"token": token, "expires": time.time() + TTL_SECONDS, "action": action}
        raise ConfirmationRequired(action=action, token=token, expires_in=TTL_SECONDS, impact=impact)

    def consume(self, action: str, params: dict[str, Any], token: str) -> None:
        self._sweep()
        fp = self.fingerprint(action, params)
        item = self._items.get(fp)
        if not item or item["token"] != token or item["action"] != action:
            raise ConfirmationRejected(
                "确认令牌无效或参数已变化（参数变化后令牌自动失效，请重新发起）"
            )
        del self._items[fp]

    def _sweep(self) -> None:
        now = time.time()
        for fp in [k for k, v in self._items.items() if v["expires"] < now]:
            del self._items[fp]
