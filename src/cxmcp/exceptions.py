"""领域异常。所有异常只走 stderr 日志，绝不在 stdout 打印。"""

from __future__ import annotations


class ChaoxingError(Exception):
    """所有 cxmcp 异常的基类。"""

    error_type = "ChaoxingError"
    guidance = ""


class LoginRequired(ChaoxingError):
    error_type = "login_required"
    guidance = (
        "未登录或会话已失效。请调用 cx_login（账号+密码），"
        "或让用户在浏览器登录学习通后用 cx_import_cookies 导入 Cookie。"
    )


class RiskControlPaused(ChaoxingError):
    """命中学习通风控（验证码 / 滑块）。按约定不自动过码，直接暂停。"""

    error_type = "risk_control_paused"
    guidance = (
        "学习通要求人机验证（验证码/滑块）。已按策略暂停，不会自动绕过。"
        "请让用户用浏览器打开学习通完成一次验证，确保登录状态正常，"
        "然后从浏览器导出最新 Cookie 并调用 cx_import_cookies 覆盖，再重试原操作。"
    )

    def __init__(self, url: str = "", detail: str = ""):
        self.url = url
        msg = f"命中风控验证: {detail or url or 'unknown'}"
        super().__init__(msg)


class VerificationRequiredLogin(ChaoxingError):
    """登录触发了二次验证/短信验证，无法用纯 HTTP 完成。"""

    error_type = "login_verification_required"
    guidance = (
        "平台对该账号要求二次验证（短信/扫码），本项目不会绕过。"
        "请让用户在浏览器或学习通 App 完成登录后，改用 cx_import_cookies。"
    )


class ConfirmationRequired(ChaoxingError):
    """高影响操作缺少一次性确认令牌。携带 token 等待用户确认后重调。"""

    error_type = "confirmation_required"

    def __init__(self, action: str, token: str, expires_in: int, impact: str):
        self.action = action
        self.token = token
        self.expires_in = expires_in
        self.impact = impact
        super().__init__(
            f"操作 [{action}] 需要用户确认。影响: {impact}。"
            f"确认令牌: {token}（{expires_in} 秒内有效，一次性）。"
            "向用户复述影响并获得明确同意后，携带 confirm_token 原样重调本工具。"
        )


class ConfirmationRejected(ChaoxingError):
    error_type = "confirmation_rejected"
    guidance = "确认令牌无效、已过期或参数已变化。请重新发起操作并再次走确认流程。"


class UpstreamChanged(ChaoxingError):
    """学习通页面/接口改版导致解析失败（HTML 选择器或 JSON 结构变了）。"""

    error_type = "upstream_changed"
    guidance = (
        "学习通返回结构与预期不符，多为平台改版。请把返回中的 snippet "
        "提供给开发者更新解析器；也可先在浏览器确认该页面当前形态。"
    )


class NotSupported(ChaoxingError):
    error_type = "not_supported"
    guidance = "该功能在当前角色（teacher/student）下不可用。"
