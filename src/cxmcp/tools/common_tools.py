"""共用工具：登录 / 会话 / 课程 / Cookie 导入。"""

from __future__ import annotations

from typing import Any

from ..api import courses as courses_api
from .common import AppContext, require_login, safe_tool


def register_common(mcp: Any, ctx: AppContext) -> None:
    @mcp.tool(
        name="cx_login",
        description=(
            "登录学习通（超星账号）。密码仅在本次调用内存中使用，不会写入日志或返回值。"
            "若平台要求二次验证（短信/扫码），会返回 login_verification_required，"
            "此时请引导用户浏览器登录后改用 cx_import_cookies。"
        ),
    )
    @safe_tool
    def cx_login(username: str, password: str) -> dict[str, Any]:
        info = ctx.session.login(username, password)
        return {"uid": info.get("uid"), "name": info.get("name"), "cookieFile": str(ctx.cfg.cookie_file)}

    @mcp.tool(
        name="cx_session_status",
        description="检查学习通登录态是否有效（回读个人空间首页判断）。",
    )
    @safe_tool
    def cx_session_status() -> dict[str, Any]:
        if ctx.session.uid is None:
            loaded = ctx.session.load_cookies()
            if not loaded:
                return {"logged_in": False, "reason": "本地无 Cookie 文件，需要 cx_login"}
        state = ctx.session.check_session()
        return state

    @mcp.tool(
        name="cx_list_courses",
        description=(
            "列出学习通课程（学生返回『我学的课』，教师返回任教课程），"
            "含 courseId/clazzId/cpi——后续所有课程相关操作都靠这三个 ID 定位。"
        ),
    )
    @safe_tool
    def cx_list_courses() -> dict[str, Any]:
        require_login(ctx)
        items = courses_api.list_courses(ctx.session)
        return {"count": len(items), "courses": items}

    @mcp.tool(
        name="cx_import_cookies",
        description=(
            "从浏览器导入学习通 Cookie（登录后 F12 复制，或用编辑器插件导出）。"
            "传入 [{name,value,domain?,path?}, ...]。适用于平台强制二次验证、"
            "密码登录被风控等场景。"
        ),
    )
    @safe_tool
    def cx_import_cookies(cookies: list[dict[str, Any]]) -> dict[str, Any]:
        count = ctx.session.import_cookies(cookies)
        state = ctx.session.check_session()
        return {"imported": count, "cookieFile": str(ctx.cfg.cookie_file), "session": state}

    @mcp.tool(
        name="cx_logout",
        description="退出学习通并删除本地 Cookie 文件。",
    )
    @safe_tool
    def cx_logout() -> dict[str, Any]:
        ctx.session.logout()
        return {"logged_out": True}
