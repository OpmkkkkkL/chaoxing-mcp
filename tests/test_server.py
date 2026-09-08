"""server 行为测试：工具注册、cx_login 流程、确认门两阶段、自动化开关。"""

import json

import pytest

from cxmcp.server import build_server
from conftest import FakeResponse, patch_http

LOGIN_PAGE = '<input id="t" name="t" value="true">'
LOGIN_OK = '{"status": true, "msg": "登录成功"}'
USERINFO = '{"msg": {"uid": 1001, "name": "张同学"}}'
IHOME_OK = "<html>欢迎 账号：张同学</html>"


def _patch_login(sess):
    return patch_http(
        sess,
        {
            "passport2.chaoxing.com/login": FakeResponse(text=LOGIN_PAGE),
            "fanyalogin": FakeResponse(text=LOGIN_OK),
            "userLogin4UAP.do": FakeResponse(text=USERINFO),
            "https://i.chaoxing.com": FakeResponse(text=IHOME_OK),
        },
    )


@pytest.mark.asyncio
async def test_teacher_server_registers_tools():
    mcp = build_server("teacher")
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "cx_login" in names and "cx_t_review_homework" in names
    assert not any(n.startswith("cx_s_") for n in names)


@pytest.mark.asyncio
async def test_student_no_automation_by_default():
    tools = await build_server("student").list_tools()
    names = {t.name for t in tools}
    assert "cx_s_auto_answer_quiz" not in names
    assert "cx_s_simulate_video_task" not in names


@pytest.mark.asyncio
async def test_automation_optin():
    tools = await build_server("student", enable_automation=True).list_tools()
    names = {t.name for t in tools}
    assert {"cx_s_auto_answer_quiz", "cx_s_simulate_video_task"} <= names


@pytest.mark.asyncio
async def test_login_and_status_flow(tmp_path):
    mcp = build_server("student", cookie_file=str(tmp_path / "c.json"))
    sess = mcp._cx_ctx.session
    p, _ = _patch_login(sess)
    with p:
        r = await mcp.call_tool("cx_login", {"username": "13800138000", "password": "pw"})
        payload = json.loads(r.content[0].text) if hasattr(r, "content") else r
        assert payload["ok"] is True
        assert payload["uid"] in ("1001", 1001)

        r2 = await mcp.call_tool("cx_session_status", {})
        p2b = json.loads(r2.content[0].text) if hasattr(r2, "content") else r2
        assert p2b["ok"] is True and p2b["logged_in"] is True


@pytest.mark.asyncio
async def test_confirmation_two_phase(tmp_path):
    """未确认时返回 token；携带 token 重调才执行。"""
    mcp = build_server("student", cookie_file=str(tmp_path / "c.json"))
    ctx = mcp._cx_ctx
    ctx.session.uid = "1001"  # 预置登录态

    p, calls = patch_http(
        ctx.session,
        {
            "https://i.chaoxing.com": FakeResponse(text=IHOME_OK),
            "backclazzdata": FakeResponse(text='{"channelList":[{"puid":1,"content":{"id":9,"cpi":3,"course":{"data":[{"id":1,"name":"测试课"}]}}}]}'),
            "stucoursemiddle": FakeResponse(
                text='<ul class="navshow"><li><a href="/work/getAllWork?classId=9&courseId=1&workRelationId=5">作业</a></li>'
                '<li><a data="/mooc-ans/mycourse/studentstudycourselist?courseid=1">章节</a></li></ul>',
                url="https://mooc1-2.chaoxing.com/visit/stucoursemiddle",
            ),
            "isExpire": FakeResponse(text='{"data": {"standardEnc": "' + "e" * 32 + '"}}'),
            "addStudentWorkNew": FakeResponse(text='{"status": true}'),
        },
    )
    args = {
        "courseRef": "测试课",
        "workUrl": "https://mooc1.chaoxing.com/mooc-ans/work/doHomeWorkNew?classId=9&courseId=1&workRelationId=5",
        "answers": [{"stem": "1", "answer": "A"}],
        "submit": True,
    }
    with p:
        r1 = await mcp.call_tool("cx_s_submit_homework", dict(args))
        d1 = json.loads(r1.content[0].text) if hasattr(r1, "content") else r1
        assert d1["ok"] is False and d1["errorType"] == "confirmation_required"
        assert d1["confirmToken"]

        # 参数不变 + token → 执行
        r2 = await mcp.call_tool("cx_s_submit_homework", {**args, "confirmToken": d1["confirmToken"]})
        d2 = json.loads(r2.content[0].text) if hasattr(r2, "content") else r2
        assert d2["ok"] is True
        posts = [u for m, u in calls if m == "POST"]
        assert any("addStudentWorkNew" in u for u in posts)
