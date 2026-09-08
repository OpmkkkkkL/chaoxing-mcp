"""API 解析测试：课程列表 / 作业 enc / 菜单 / 章节 / 附件下载。"""

import pytest

from cxmcp.api import chapters as chapters_api
from cxmcp.api import courses as courses_api
from cxmcp.api import work as work_api
from cxmcp.exceptions import UpstreamChanged
from cxmcp.session import ChaoxingSession
from conftest import FakeResponse, make_cfg, patch_http

BACKCLAZZDATA = """
{"channelList": [
  {"roleId": 0, "puid": 88, "content": {"id": 90001, "cpi": 77,
    "course": {"data": [{"id": 12345, "name": "高等数学",
      "teacherList": [{"name": "李老师"}]}]}}},
  {"content": "not-a-dict"},
  {"content": {"id": "junk"}}
]}
"""

MENU_HTML = """
<ul class="navshow">
  <li><a href="javascript:;">章节</a><a data="/mooc-ans/mycourse/studentstudycourselist?courseid=12345&clazzid=90001&cpi=77" href="javascript:;"></a></li>
  <li><a href="/work/getAllWork?classId=90001&courseId=12345&type=&enc=aaa">作业</a></li>
</ul>
"""

IS_EXPIRE = '{"data": {"standardEnc": "abc123def456abc123def456abc12345"}}'

DETAIL_HTML = """
<div class="TiMu"><div class="Zy_TItle">1.（单选）中国的首都是？</div>
  <ul class="Zy_ulTop"><li>A. 上海</li><li>B. 北京</li></ul></div>
<iframe objectid="aabbccdd" filename="讲义.docx"></iframe>
"""

ATTACH_PAGE = '<a class="btnDown" href="https://pan.chaoxing.com/file/xyz.docx">下载</a>'


def _sess(tmp_path):
    return ChaoxingSession(make_cfg(tmp_path))


def test_list_courses_defensive(tmp_path):
    sess = _sess(tmp_path)
    p, _ = patch_http(sess, {"backclazzdata": FakeResponse(text=BACKCLAZZDATA)})
    with p:
        courses = courses_api.list_courses(sess)
    assert len(courses) == 1  # 坏数据被跳过
    c = courses[0]
    assert c["courseId"] == 12345 and c["clazzId"] == 90001 and c["cpi"] == 77
    assert c["teacher"] == "李老师"


def test_resolve_course(tmp_path):
    courses = [{"name": "高等数学", "courseId": 12345, "clazzId": 1, "cpi": 1}]
    assert courses_api.resolve_course(courses, "12345")["name"] == "高等数学"
    assert courses_api.resolve_course(courses, "高等数")["courseId"] == 12345
    with pytest.raises(UpstreamChanged):
        courses_api.resolve_course(courses, "不存在")


def test_menu_parse_data_attribute(tmp_path):
    sess = _sess(tmp_path)
    course = {"name": "高数", "courseId": 12345, "clazzId": 90001, "cpi": 77}
    p, _ = patch_http(sess, {"stucoursemiddle": FakeResponse(text=MENU_HTML, url="https://mooc1-2.chaoxing.com/visit/stucoursemiddle")})
    with p:
        menu = chapters_api.get_menu(sess, course)
    names = [m["name"] for m in menu]
    assert "章节" in names and "作业" in names
    work_url = next(m["url"] for m in menu if m["name"] == "作业")
    assert "getAllWork" in work_url


def test_homework_enc_flow(tmp_path):
    sess = _sess(tmp_path)
    course = {"name": "高数", "courseId": 12345, "clazzId": 90001, "cpi": 77}
    work_url = "https://mooc1.chaoxing.com/mooc-ans/work/doHomeWorkNew?classId=90001&courseId=12345&workRelationId=555"
    p, _ = patch_http(
        sess,
        {
            "stucoursemiddle": FakeResponse(text=MENU_HTML, url="https://mooc1-2.chaoxing.com/visit/stucoursemiddle"),
            "isExpire": FakeResponse(text=IS_EXPIRE),
        },
    )
    with p:
        enc, ids = work_api.get_standard_enc(sess, course, work_url)
        assert enc == "abc123def456abc123def456abc12345"
        assert ids["workRelationId"] == "555"


def test_homework_detail_parse(tmp_path):
    sess = _sess(tmp_path)
    course = {"name": "高数", "courseId": 12345, "clazzId": 90001, "cpi": 77}
    work_url = "https://mooc1.chaoxing.com/mooc-ans/work/doHomeWorkNew?classId=90001&courseId=12345&workRelationId=555"
    p, _ = patch_http(
        sess,
        {
            "isExpire": FakeResponse(text=IS_EXPIRE),
            "doHomeWorkNew": FakeResponse(text=DETAIL_HTML, url=work_url),
        },
    )
    with p:
        detail = work_api.get_homework_detail(sess, course, work_url)
    assert detail["questionCount"] == 1
    assert detail["questions"][0]["type"] == "single"
    assert detail["attachments"][0]["objectId"] == "aabbccdd"


def test_attachment_download(tmp_path):
    sess = _sess(tmp_path)
    p, _ = patch_http(
        sess,
        {
            "ueditorupload/read": FakeResponse(text=ATTACH_PAGE, url="https://mooc1.chaoxing.com/mooc-ans/ueditorupload/read"),
            "pan.chaoxing.com": FakeResponse(text=b"binary-data-here", url="https://pan.chaoxing.com/file/xyz.docx"),
        },
    )
    with p:
        out = work_api.download_attachment(sess, "aabbccdd", str(tmp_path / "dl"))
    assert out["size"] == 16
    assert (tmp_path / "dl").exists()


# ------------------------------------------------------------------ 实机模板（2026-09 真实页面结构）
REAL_WORK_HTML = """
<li class="lookLi">
  <div class="titTxt" data="0">
    <p class="clearfix"><a href="/mooc-ans/work/viewWork?id=54210547&courseId=1&classId=9&workId=8ce0c4&isdisplaytable=2&ut=s&mooc=1&enc=83c640750c73a1dc6861b6b9f5e45827&workSystem=0&cpi=3" title="第一章作业" data="54210547" class="removeReddot">第一章作业 ...</a></p>
    <p>开始时间： 2026-06-18 08:22 截止时间： 2026-07-02 08:22 作业状态： 已过期</p>
  </div>
</li>
<li class="lookLi">
  <div class="titTxt" data="0">
    <p class="clearfix"><a href="/mooc-ans/work/viewWork?id=54210548&courseId=1&classId=9&workId=abcd&enc=1234567890abcdef1234567890abcdef&cpi=3" title="第二章作业" data="54210548" class="removeReddot">第二章作业</a></p>
    <p>作业状态： 已完成</p>
  </div>
</li>
"""


def test_list_homeworks_real_template(tmp_path):
    """实测模板解析（2026-09）：li.lookLi + a.removeReddot。"""
    sess = _sess(tmp_path)
    course = {"name": "测试课", "courseId": 1, "clazzId": 9, "cpi": 3}
    p, _ = patch_http(
        sess,
        {
            "stucoursemiddle": FakeResponse(
                text='<ul class="navshow"><li><a href="/work/getAllWork?classId=9&courseId=1">作业</a></li></ul>',
                url="https://mooc1-2.chaoxing.com/visit/stucoursemiddle",
            ),
            "getAllWork": FakeResponse(text=REAL_WORK_HTML, url="https://mooc1-2.chaoxing.com/work/getAllWork"),
        },
    )
    with p:
        rows = work_api.list_homeworks(sess, course)
    assert len(rows) == 2
    first = rows[0]
    assert first["title"] == "第一章作业"
    assert first["status"] == "已过期"
    assert first["deadline"] == "2026-07-02 08:22"
    assert first["workId"] == "54210547"
    assert "enc=83c640750c73a1dc6861b6b9f5e45827" in first["url"]
