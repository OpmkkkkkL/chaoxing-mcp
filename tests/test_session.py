"""登录流程 / Cookie 持久化 / 风控守卫测试。"""

import json

import pytest

from cxmcp.exceptions import LoginRequired, RiskControlPaused
from cxmcp.session import ChaoxingSession
from conftest import FakeResponse, make_cfg, patch_http

LOGIN_PAGE = '<input type="hidden" id="t" name="t" value="true"><form id="fanyalogin">'
LOGIN_OK = '{"status": true, "msg": "恭喜您，登录成功！"}'
LOGIN_FAIL = '{"status": false, "msg2": "账号或密码错误"}'
LOGIN_CAPTCHA = '{"status": false, "msg": "请输入验证码"}'
USERINFO = '{"result": 1, "msg": {"uid": 1001, "name": "张同学"}}'
IHOME_OK = "<html>欢迎 账号：张同学</html>"


def test_login_success(tmp_path):
    sess = ChaoxingSession(make_cfg(tmp_path))
    p, calls = patch_http(
        sess,
        {
            "passport2.chaoxing.com/login": FakeResponse(text=LOGIN_PAGE),
            "fanyalogin": FakeResponse(text=LOGIN_OK),
            "userLogin4UAP.do": FakeResponse(text=USERINFO),
            "i.chaoxing.com": FakeResponse(text=IHOME_OK),
        },
    )
    with p:
        info = sess.login("13800138000", "secret")
        assert str(info["uid"]) == "1001"
        assert sess.uid
    # Cookie 已原子落盘
    saved = json.loads((tmp_path / "student_cookies.json").read_text())
    assert "cookies" in saved and saved["uid"]
    # 密码不出现在任何请求 URL 中
    assert all("secret" not in u for _, u in calls)


def test_login_bad_password(tmp_path):
    sess = ChaoxingSession(make_cfg(tmp_path))
    p, _ = patch_http(
        sess,
        {
            "passport2.chaoxing.com/login": FakeResponse(text=LOGIN_PAGE),
            "fanyalogin": FakeResponse(text=LOGIN_FAIL),
        },
    )
    with p, pytest.raises(LoginRequired):
        sess.login("13800138000", "wrong")


def test_login_captcha_pauses(tmp_path):
    sess = ChaoxingSession(make_cfg(tmp_path))
    p, _ = patch_http(
        sess,
        {
            "passport2.chaoxing.com/login": FakeResponse(text=LOGIN_PAGE),
            "fanyalogin": FakeResponse(text=LOGIN_CAPTCHA, url="https://x/ok"),
        },
    )
    with p, pytest.raises(RiskControlPaused):
        sess.login("13800138000", "pw")


def test_risk_control_on_202(tmp_path):
    sess = ChaoxingSession(make_cfg(tmp_path))
    p, _ = patch_http(
        sess, {"anything": FakeResponse(status_code=202, text="", url="https://x/ok")}
    )
    with p, pytest.raises(RiskControlPaused):
        sess.get("https://x.chaoxing.com/anything")


def test_cookie_import_and_check(tmp_path):
    sess = ChaoxingSession(make_cfg(tmp_path))
    n = sess.import_cookies(
        [
            {"name": "_uid", "value": "1001", "domain": ".chaoxing.com"},
            {"name": "UID", "value": "1001"},
            {"name": "bad"},  # 缺 value，应被忽略
        ]
    )
    assert n == 2
    p, _ = patch_http(sess, {"i.chaoxing.com": FakeResponse(text=IHOME_OK)})
    with p:
        state = sess.check_session()
        assert state["logged_in"] is True


def test_ensure_login_without_cookie(tmp_path):
    sess = ChaoxingSession(make_cfg(tmp_path))
    with pytest.raises(LoginRequired):
        sess.ensure_login()
