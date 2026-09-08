"""MCP server 组装：build_server(role) -> MCPServer。"""

from __future__ import annotations

from . import __version__
from .config import load_config
from .tools import automation_tools, common_tools, student, teacher
from .tools.common import AppContext

ROLE_INSTRUCTIONS = {
    "teacher": (
        "学习通教师端助手。读取操作直接执行；发布、批改、发通知、上传、发起签到等"
        "高影响操作会返回 confirmation_required，必须向用户复述影响并获得明确同意后，"
        "携带 confirmToken 原样重调。登录失效返回 login_required 时引导用户 cx_login "
        "或 cx_import_cookies。"
    ),
    "student": (
        "学习通学生端助手。课程/作业/考试/资料为只读操作；作业正式提交、照片签到等"
        "高影响操作会返回 confirmation_required，必须向用户复述影响并获得明确同意后，"
        "携带 confirmToken 原样重调。命中风控（risk_control_paused）时按指引让用户"
        "浏览器过验证后 cx_import_cookies，不要重试。"
    ),
}


def build_server(
    role: str,
    enable_automation: bool = False,
    cookie_file: str | None = None,
):
    """构建 MCP server。role: 'teacher' | 'student'。"""
    from mcp.server import MCPServer

    cfg = load_config(role, cookie_file=cookie_file, enable_automation=enable_automation)
    ctx = AppContext(cfg)

    display = "教师版" if role == "teacher" else "学生版"
    mcp = MCPServer(
        name=f"chaoxing-{role}",
        title=f"学习通{display} MCP",
        description=f"超星学习通{display}（cxmcp v{__version__}，纯 HTTP 协议）",
        instructions=ROLE_INSTRUCTIONS[role],
        version=__version__,
    )

    common_tools.register_common(mcp, ctx)
    if role == "teacher":
        teacher.register_teacher(mcp, ctx)
    else:
        student.register_student(mcp, ctx)
        if cfg.enable_automation:
            automation_tools.register_automation(mcp, ctx)
    mcp._cx_ctx = ctx  # 供测试与高级集成访问
    return mcp
