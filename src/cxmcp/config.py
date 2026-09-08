"""全局配置：环境变量 + CLI 参数合并。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COOKIE_DIR = Path.home() / ".chaoxing-mcp"


@dataclass
class Config:
    role: str                      # "teacher" | "student"
    cookie_file: Path
    request_timeout: int = 20
    enable_automation: bool = False


def load_config(
    role: str,
    cookie_file: str | None = None,
    enable_automation: bool = False,
    request_timeout: int | None = None,
) -> Config:
    """优先级：CLI 参数 > 环境变量 > 默认值。"""
    env_cookie = os.environ.get("CX_COOKIE_FILE")
    path = Path(cookie_file or env_cookie or (DEFAULT_COOKIE_DIR / f"{role}_cookies.json"))

    timeout = request_timeout
    if timeout is None:
        try:
            timeout = int(os.environ.get("CX_REQUEST_TIMEOUT", "20"))
        except ValueError:
            timeout = 20

    auto = enable_automation or os.environ.get("CX_ENABLE_AUTOMATION", "").lower() in (
        "1", "true", "yes",
    )
    return Config(
        role=role,
        cookie_file=path.expanduser(),
        request_timeout=timeout,
        enable_automation=auto,
    )
