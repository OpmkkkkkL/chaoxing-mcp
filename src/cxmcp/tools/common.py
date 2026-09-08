"""工具层基础设施：应用上下文 + 统一错误包装 + 课程解析辅助。"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable

from ..config import Config
from ..confirm import ConfirmationStore
from ..exceptions import (
    ChaoxingError,
    ConfirmationRequired,
    LoginRequired,
)
from ..session import ChaoxingSession

log = logging.getLogger("cxmcp.tools")


class AppContext:
    """进程级单例：配置 + 会话 + 确认门。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = ChaoxingSession(cfg)
        self.confirms = ConfirmationStore()


def safe_tool(fn: Callable) -> Callable:
    """把领域异常折叠成结构化结果，绝不让 MCP 会话崩掉。"""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return {"ok": True, **(fn(*args, **kwargs) or {})}
        except ConfirmationRequired as e:
            return {
                "ok": False,
                "errorType": e.error_type,
                "confirmToken": e.token,
                "expiresIn": e.expires_in,
                "impact": e.impact,
                "error": str(e),
            }
        except ChaoxingError as e:
            log.warning("工具 %s 失败: %s", fn.__name__, e)
            return {
                "ok": False,
                "errorType": e.error_type,
                "error": str(e),
                "guidance": getattr(e, "guidance", ""),
            }
        except Exception as e:  # noqa: BLE001
            log.exception("工具 %s 内部错误", fn.__name__)
            return {"ok": False, "errorType": "internal", "error": f"{type(e).__name__}: {e}"}

    return wrapper


def require_login(ctx: AppContext) -> ChaoxingSession:
    try:
        ctx.session.ensure_login()
    except LoginRequired:
        raise
    return ctx.session


def confirmed(ctx: AppContext, action: str, params: dict[str, Any], impact: str,
              token: str | None) -> None:
    """无 token 则签发（抛 ConfirmationRequired），有 token 则核销。"""
    if token is None:
        ctx.confirms.issue(action, params, impact)
    ctx.confirms.consume(action, params, token)


def require_course(ctx: AppContext, ref: str) -> dict[str, Any]:
    """登录 + 拉课程列表 + 解析目标课程。"""
    from ..api import courses as courses_api

    require_login(ctx)
    all_courses = courses_api.list_courses(ctx.session)
    return courses_api.resolve_course(all_courses, ref)
