"""HTTP 会话：登录、Cookie 持久化、风控守卫、TLS 兼容。

要点（来自逆向研究）：
- 学习通服务器 TLS 配置较老，需要 verify=False + SECLEVEL=1 加密套件；
- 命中风控的信号：HTTP 202 或跳转 URL 含 antispiderShowVerify；
- Cookie 存 JSON（含 name/value/domain/path），临时文件 0o600 原子替换；
- 日志只走 stderr，本模块绝不 print 到 stdout。
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from .config import Config
from .crypto import encrypt_aes
from .exceptions import (
    LoginRequired,
    RiskControlPaused,
    UpstreamChanged,
    VerificationRequiredLogin,
)

log = logging.getLogger("cxmcp.session")  # handler 由 cli 挂到 stderr

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

PASSPORT = "https://passport2.chaoxing.com"
SSO = "https://sso.chaoxing.com"
IHOME = "https://i.chaoxing.com"
MOOC1_API = "https://mooc1-api.chaoxing.com"


class _LegacyTLSAdapter(HTTPAdapter):
    """兼容学习通老 TLS / 弱加密套件。"""

    def init_poolmanager(self, *args: Any, **kwargs: Any):  # noqa: ANN401
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except ssl.SSLError:  # pragma: no cover - 平台相关
            log.warning("SECLEVEL=1 不可用，使用默认套件")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class ChaoxingSession:
    """携带 Cookie 的 requests 会话 + 登录态管理。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.http = requests.Session()
        for prefix in ("https://", "http://"):
            self.http.mount(prefix, _LegacyTLSAdapter())
        self.http.headers.update(
            {
                "User-Agent": UA,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": IHOME + "/",
            }
        )
        self.uid: str | None = None
        self.uname: str | None = None

    # ---------------------------------------------------------- HTTP 封装
    @staticmethod
    def _guard(resp: requests.Response) -> requests.Response:
        """风控守卫：202 / antispider 跳转 / 会话被顶掉返回登录 HTML 即暂停。"""
        if resp.status_code == 202 or "antispiderShowVerify" in (resp.url or ""):
            raise RiskControlPaused(url=str(resp.url))
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "html" in ctype and len(resp.text) > 200:
            head = resp.text[:2000]
            if "passport2.chaoxing.com" in head or "name=\"password\"" in head:
                # 会话失效被重定向到登录页
                raise LoginRequired("平台将会话重定向到登录页，Cookie 已失效或被刷新")
            if "antispider" in head or "processVerify" in head:
                raise RiskControlPaused(url=str(resp.url), detail="响应为风控验证页")
        return resp

    def get(self, url: str, **kw: Any) -> requests.Response:
        kw.setdefault("timeout", self.cfg.request_timeout)
        return self._guard(self.http.get(url, verify=False, **kw))

    def post(self, url: str, **kw: Any) -> requests.Response:
        kw.setdefault("timeout", self.cfg.request_timeout)
        return self._guard(self.http.post(url, verify=False, **kw))

    def get_json(self, url: str, **kw: Any) -> Any:
        resp = self.get(url, **kw)
        try:
            return resp.json()
        except ValueError as exc:
            raise UpstreamChanged(f"{url} 未返回 JSON: {resp.text[:200]}") from exc

    # ---------------------------------------------------------- 登录
    def login(self, username: str, password: str) -> dict[str, Any]:
        """账号密码登录（纯 HTTP，不处理二次验证）。"""
        # 1) 预登录，取隐藏域 t 决定是否加密
        page = self.get(
            f"{PASSPORT}/login",
            params={"newversion": "true", "fid": -1, "refer": IHOME},
        )
        t_value = self._parse_t_flag(page.text)
        pwd = encrypt_aes(password) if t_value else password

        # 2) fanyalogin
        resp = self.post(
            f"{PASSPORT}/fanyalogin",
            data={
                "fid": -1,
                "uname": username,
                "password": pwd,
                "refer": IHOME,
                "t": "true" if t_value else "false",
                "forbidotherlogin": 0,
                "validate": "",
                "doubleFactorLogin": 0,
                "independentId": 0,
            },
        )
        data = self._safe_json(resp)
        msg = str(data.get("msg") or data.get("msg2") or "")
        status = data.get("status")
        if "验证码" in msg or "滑块" in msg:
            raise RiskControlPaused(url=f"{PASSPORT}/fanyalogin", detail=msg)
        if "二次验证" in msg or "doubleFactor" in msg or "扫码" in msg:
            raise VerificationRequiredLogin(msg)
        if status is not True and "登录成功" not in msg:
            raise LoginRequired(f"登录失败: {msg or resp.text[:200]}")

        # 3) 用户信息（防御性解析：msg 字段可能不是 dict）
        uid, realname = None, None
        try:
            info = self.get_json(f"{SSO}/apis/login/userLogin4UAP.do")
            payload = info.get("msg") if isinstance(info.get("msg"), dict) else info.get("data")
            if isinstance(payload, dict):
                uid = str(payload.get("uid") or payload.get("puid") or "")
                realname = payload.get("name") or payload.get("realname")
        except Exception:  # noqa: BLE001 - 用户信息失败不阻断登录
            log.warning("获取用户信息失败，继续使用 Cookie 会话")

        self.uid = uid or self._cookie_value("_uid") or self._cookie_value("UID")
        self.uname = realname or username
        self.save_cookies()
        log.info("登录成功 uid=%s", self.uid)
        return {"uid": self.uid, "name": self.uname, "fid": self._cookie_value("fid")}

    @staticmethod
    def _parse_t_flag(html: str) -> bool:
        try:
            soup = BeautifulSoup(html, "html.parser")
            node = soup.find("input", attrs={"id": "t"}) or soup.find(
                "input", attrs={"name": "t"}
            )
            if node and node.get("value"):
                return str(node["value"]).lower() == "true"
        except Exception:  # noqa: BLE001
            pass
        # 兜底正则
        import re

        m = re.search(r'name="t"[^>]*value="(true|false)"', html)
        return bool(m and m.group(1).lower() == "true")

    def _safe_json(self, resp: requests.Response) -> dict[str, Any]:
        try:
            data = resp.json()
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    # ---------------------------------------------------------- Cookie
    def _cookie_value(self, name: str) -> str | None:
        c = self.http.cookies.get(name)
        return str(c) if c is not None else None

    def _cookie_path(self) -> Path:
        return Path(self.cfg.cookie_file)

    def save_cookies(self) -> None:
        path = self._cookie_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": int(time.time()),
            "uid": self.uid,
            "cookies": [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "expires": c.expires,
                }
                for c in self.http.cookies
            ],
        }
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, path)  # 原子替换
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load_cookies(self) -> bool:
        path = self._cookie_path()
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("Cookie 文件损坏: %s", path)
            return False
        jar = self.http.cookies
        for item in payload.get("cookies", []):
            if not all(k in item for k in ("name", "value")):
                continue
            jar.set(
                item["name"],
                item["value"],
                domain=item.get("domain") or ".chaoxing.com",
                path=item.get("path") or "/",
            )
        self.uid = payload.get("uid") or self._cookie_value("_uid")
        return True

    def import_cookies(self, cookies: list[dict[str, Any]]) -> int:
        """从浏览器导出的 Cookie 列表导入（name/value/domain/path）。"""
        count = 0
        for item in cookies:
            if isinstance(item, dict) and item.get("name") and item.get("value"):
                self.http.cookies.set(
                    item["name"],
                    str(item["value"]),
                    domain=item.get("domain") or ".chaoxing.com",
                    path=item.get("path") or "/",
                )
                count += 1
        self.uid = self._cookie_value("_uid") or self._cookie_value("UID") or self.uid
        if count:
            self.save_cookies()
        return count

    def export_cookies(self) -> list[dict[str, Any]]:
        return [
            {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            for c in self.http.cookies
        ]

    # ---------------------------------------------------------- 会话检查
    def check_session(self) -> dict[str, Any]:
        """回读个人空间首页判断登录态。"""
        try:
            resp = self.get(IHOME + "/")
        except RiskControlPaused:
            raise
        except Exception as exc:  # noqa: BLE001
            return {"logged_in": False, "reason": f"网络错误: {exc}"}
        text = resp.text[:20000]
        if "账号：" in text or "账号:" in text or "欢迎" in text:
            return {"logged_in": True, "uid": self.uid, "name": self.uname}
        if "login" in (resp.url or ""):
            return {"logged_in": False, "reason": "被重定向到登录页"}
        return {
            "logged_in": False,
            "reason": "页面未包含登录标记",
            "snippet": text[:200],
        }

    def ensure_login(self) -> None:
        """有 Cookie 就加载并校验；校验失败抛 LoginRequired。"""
        if self.uid is None:
            self.load_cookies()
        if self.uid is not None:
            state = self.check_session()
            if state.get("logged_in"):
                return
            log.info("Cookie 会话失效: %s", state.get("reason"))
            raise LoginRequired("Cookie 已失效")
        raise LoginRequired("尚未登录")

    def logout(self) -> None:
        self.uid = None
        self.uname = None
        self.http.cookies.clear()
        try:
            self._cookie_path().unlink(missing_ok=True)
        except OSError:
            pass


def cookie_file_hint(cfg: Config) -> str:
    return f"{cfg.cookie_file} (host: {urlparse(cfg.cookie_file.as_uri()).scheme})" if False else str(cfg.cookie_file)
