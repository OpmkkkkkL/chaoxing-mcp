"""空状态判别 + 章节树解析测试。

覆盖两类真实事故：
1. 列表页确实没有内容时，不能抛 UpstreamChanged（模板改版）；
2. 章节树容器 .timeline 为空 = 老师未发布章节，返回 [] 而不是报错。
"""

import pytest

from cxmcp.api import chapters as chapters_api
from cxmcp.api import exams as exams_api
from cxmcp.api import files as files_api
from cxmcp.api import pagestate, teacher as teacher_api
from cxmcp.api import work as work_api
from cxmcp.exceptions import UpstreamChanged
from cxmcp.session import ChaoxingSession
from conftest import FakeResponse, patch_http

COURSE = {"name": "高数", "courseId": 12345, "clazzId": 90001, "cpi": 77}

HOME_URL = "https://mooc1-2.chaoxing.com/visit/stucoursemiddle"


def _sess(tmp_path):
    return ChaoxingSession(_cfg(tmp_path))


def _cfg(tmp_path):
    from conftest import make_cfg

    return make_cfg(tmp_path)


def _menu_html(target_kw, url):
    return f"""
    <ul class="navshow">
      <li><a href="{url}">{target_kw}</a></li>
    </ul>
    """


# --------------------------------------------------------------- pagestate
def test_visible_text_ignores_script():
    html = "<div><script>var t='暂无内容';</script><p>这里有 3 条作业</p></div>"
    assert pagestate.visible_text(html) == "这里有 3 条作业"
    assert not pagestate.is_empty_page(html)


def test_is_empty_page_markers():
    assert pagestate.is_empty_page("<div>我的作业 暂无内容 确定</div>")
    assert pagestate.is_empty_page("<div>尚未发布</div>")
    assert pagestate.is_empty_page("<div>No Data</div>")
    assert not pagestate.is_empty_page("<div>作业列表</div>")


def test_visible_text_does_not_mutate_soup():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<div><script>x</script><b>正文</b></div>", "html.parser")
    before = len(soup.find_all("script"))
    pagestate.visible_text(soup)
    assert len(soup.find_all("script")) == before  # script 未被 decompose 掉


# --------------------------------------------------------------- 作业/考试
EMPTY_WORK_PAGE = """
<html><body><div class="right-content">
  <span class="tit">我的作业</span><span class="pipe">|</span><span>待批作业</span>
  <div class="noContent">暂无内容</div>
</div></body></html>
"""

JUNK_PAGE = "<html><body><div class='whatever'>页面结构完全陌生</div></body></html>"


def test_homework_empty_page_returns_zero(tmp_path):
    sess = _sess(tmp_path)
    routes = {
        "stucoursemiddle": FakeResponse(text=_menu_html("作业", "/work/getAllWork?classId=90001&courseId=12345"), url=HOME_URL),
        "getAllWork": FakeResponse(text=EMPTY_WORK_PAGE, url="https://mooc1-2.chaoxing.com/work/getAllWork"),
    }
    p, _ = patch_http(sess, routes)
    with p:
        assert work_api.list_homeworks(sess, COURSE) == []


def test_homework_unrecognized_page_still_raises(tmp_path):
    """没有内容行、也没有空状态文案 → 仍然要报模板改版，不能被吞掉。"""
    sess = _sess(tmp_path)
    routes = {
        "stucoursemiddle": FakeResponse(text=_menu_html("作业", "/work/getAllWork?classId=90001&courseId=12345"), url=HOME_URL),
        "getAllWork": FakeResponse(text=JUNK_PAGE, url="https://mooc1-2.chaoxing.com/work/getAllWork"),
    }
    p, _ = patch_http(sess, routes)
    with p:
        with pytest.raises(UpstreamChanged):
            work_api.list_homeworks(sess, COURSE)


def test_exam_empty_page_returns_zero(tmp_path):
    sess = _sess(tmp_path)
    routes = {
        "stucoursemiddle": FakeResponse(text=_menu_html("考试", "/exam-ans/exam/test?classId=90001"), url=HOME_URL),
        "exam/test": FakeResponse(text=EMPTY_WORK_PAGE, url="https://mooc1-2.chaoxing.com/exam-ans/exam/test"),
    }
    p, _ = patch_http(sess, routes)
    with p:
        assert exams_api.list_exams(sess, COURSE) == []


def test_materials_empty_page_returns_zero(tmp_path):
    sess = _sess(tmp_path)
    routes = {
        "stucoursemiddle": FakeResponse(text=_menu_html("资料", "/coursedata?classId=90001"), url=HOME_URL),
        "coursedata": FakeResponse(text=EMPTY_WORK_PAGE, url="https://mooc1-2.chaoxing.com/coursedata"),
    }
    p, _ = patch_http(sess, routes)
    with p:
        assert files_api.list_materials(sess, COURSE) == []


def test_gradebook_empty_page(tmp_path):
    sess = _sess(tmp_path)
    routes = {
        "stucoursemiddle": FakeResponse(text=_menu_html("成绩", "/mooc-ans/moocAnalysis/grade"), url=HOME_URL),
        "grade": FakeResponse(text=EMPTY_WORK_PAGE, url="https://mooc1-2.chaoxing.com/grade"),
    }
    p, _ = patch_http(sess, routes)
    with p:
        res = teacher_api.get_gradebook(sess, COURSE)
    assert res["students"] == [] and res["empty"] is True


# --------------------------------------------------------------- 章节树
TIMELINE_HTML = """
<div class="timeline">
  <!-- 第一级开始 -->
  <div class="levelone units"><h3 class="clearfix">
    <a href="javascript:;"><em class="knowledgeOpenBtn"></em>
      <span class="articlename" title="第一章 网络体系结构">第一章 网络体系结构</span></a></h3>
    <div class="leveltwo"><h3 class="clearfix">
      <a href="/mooc-ans/mycourse/studentstudy?chapterId=1001&amp;courseId=12345&amp;clazzid=90001">
        <span class="chapterNumber">1.1</span>
        <span class="articlename" title="OSI 七层模型">OSI 七层模型</span></a>
      <em class="orange">3</em></h3>
      <div class="levelthree"><h3 class="clearfix">
        <a href="/mooc-ans/mycourse/studentstudy?chapterId=1002&amp;courseId=12345">
          <span class="articlename" title="物理层">物理层</span></a></h3></div>
    </div>
    <div class="leveltwo"><h3 class="clearfix">
      <a href="/mooc-ans/mycourse/studentstudy?chapterId=1003&amp;courseId=12345">
        <span class="chapterNumber">1.2</span>
        <span class="articlename" title="TCP/IP">TCP/IP</span></a></h3>
      <p><a href="/some/other">附件</a></p></div>
  </div>
  <!-- 第一级结束 -->
</div>
"""

EMPTY_TIMELINE_HTML = """
<div class="content1"><div class="timeline">
  <!-- 第一级开始 -->
  <!-- 第一级结束 -->
</div></div>
"""


def test_parse_chapter_tree_levels_and_ids():
    chapters = chapters_api.parse_chapter_tree(TIMELINE_HTML, base_url=HOME_URL)
    assert [c["level"] for c in chapters] == [1, 2, 3, 2]
    assert chapters[0]["title"] == "第一章 网络体系结构"
    assert chapters[1]["title"] == "1.1 OSI 七层模型"
    assert chapters[1]["chapterId"] == 1001
    assert chapters[1]["unit"] == "第一章 网络体系结构"
    assert chapters[1]["taskCount"] == 3
    assert chapters[1]["url"].startswith("https://mooc1-2.chaoxing.com/mooc-ans/mycourse/studentstudy")
    assert chapters[2]["title"] == "物理层" and chapters[2]["chapterId"] == 1002
    assert chapters[3]["title"] == "1.2 TCP/IP"


def test_list_chapters_from_timeline(tmp_path):
    sess = _sess(tmp_path)
    routes = {"stucoursemiddle": FakeResponse(text=TIMELINE_HTML, url=HOME_URL)}
    p, _ = patch_http(sess, routes)
    with p:
        chapters = chapters_api.list_chapters(sess, COURSE)
    assert len(chapters) == 4


def test_list_chapters_empty_timeline_returns_zero(tmp_path):
    """核心回归：容器为空 = 未发布章节，绝不能抛『JS 动态加载/模板改版』。"""
    sess = _sess(tmp_path)
    routes = {"stucoursemiddle": FakeResponse(text=EMPTY_TIMELINE_HTML, url=HOME_URL)}
    p, _ = patch_http(sess, routes)
    with p:
        assert chapters_api.list_chapters(sess, COURSE) == []


def test_list_chapters_no_timeline_falls_back_then_raises(tmp_path):
    sess = _sess(tmp_path)
    routes = {"stucoursemiddle": FakeResponse(text=JUNK_PAGE, url=HOME_URL)}
    p, _ = patch_http(sess, routes)
    with p:
        with pytest.raises(UpstreamChanged):
            chapters_api.list_chapters(sess, COURSE)
