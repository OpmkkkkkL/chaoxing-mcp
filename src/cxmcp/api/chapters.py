"""课程主页菜单 + 章节/任务点。

课程主页: https://mooc1-2.chaoxing.com/visit/stucoursemiddle?courseid=&clazzid=&vc=1&cpi=
  （会 302 到 /mooc-ans/mycourse/studentcourse）
菜单项: ul.navshow > li > a；很多真实 URL 藏在 <a data="..."> 属性里。
章节树: 主页 `<div class="timeline">` 容器，服务端渲染；容器为空 = 尚未发布章节。
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession

log = logging.getLogger("cxmcp.chapters")

MOOC1_2 = "https://mooc1-2.chaoxing.com"


def course_home_url(course: dict[str, Any]) -> str:
    return (
        f"{MOOC1_2}/visit/stucoursemiddle"
        f"?courseid={course['courseId']}&clazzid={course['clazzId']}&vc=1&cpi={course.get('cpi') or 0}"
    )


def get_menu(sess: ChaoxingSession, course: dict[str, Any]) -> list[dict[str, str]]:
    """解析课程左侧菜单，返回 [{name, url}]。

    模板形态：菜单项常是 <li><a>章节名</a><a data="真实URL" href="javascript:;"></a></li>
    即文本与 URL 分属两个 <a>，必须在 <li> 层配对。
    """
    resp = sess.get(course_home_url(course))
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def _real_url(a) -> str:
        href = (a.get("href") or "").strip()
        real = (a.get("data") or "").strip()
        return real or href

    nav_lists = soup.select("ul.navshow, .navshow, ul.nav, #navShow")
    containers = nav_lists or [soup]
    for ul in containers:
        for li in ul.find_all("li"):
            anchors = li.find_all("a")
            if not anchors:
                continue
            name = li.get_text(strip=True)
            url = ""
            for a in anchors:
                candidate = _real_url(a)
                if candidate and not candidate.startswith(("javascript:", "#")):
                    url = candidate
                    break
            if not url or not name:
                continue
            final = urljoin(str(resp.url), url)
            if final not in seen:
                seen.add(final)
                items.append({"name": name[:40], "url": final})

    # 兜底：无 li 结构时逐个 a 处理
    if not items:
        for a in soup.find_all("a"):
            url = _real_url(a)
            name = a.get_text(strip=True)
            if not url or not name or url.startswith(("javascript:", "#")):
                continue
            final = urljoin(str(resp.url), url)
            if final not in seen:
                seen.add(final)
                items.append({"name": name[:40], "url": final})

    if not items:
        raise UpstreamChanged("课程主页未解析到菜单")
    return items


def find_menu_url(sess: ChaoxingSession, course: dict[str, Any], keyword: str) -> str:
    """在菜单里按关键词（如 作业/章节/考试/资料）找 URL。"""
    menu = get_menu(sess, course)
    for item in menu:
        if keyword in item["name"]:
            return item["url"]
    raise UpstreamChanged(
        f"菜单中未找到含『{keyword}』的项。当前菜单: " + " | ".join(i["name"] for i in menu)
    )


# ------------------------------------------------------------------ 章节
_LEVEL_CLASSES = {"levelone": 1, "leveltwo": 2, "levelthree": 3, "unit": 1}


def parse_chapter_tree(node, base_url: str = "") -> list[dict[str, Any]]:
    """解析章节树容器（`.timeline`），返回带层级的扁平列表。

    实机形态（2026-09 校准，mooc-ans/mycourse/studentcourse 页服务端渲染）::

        <div class="timeline">
          <!-- 第一级开始 -->
          <div class="levelone units"><h3 class="clearfix">
            <a href="javascript:;"><span class="articlename" title="第一章 概述">…</span></a></h3>
            <div class="leveltwo"><h3 class="clearfix">
              <a href="/mooc-ans/mycourse/studentstudy?chapterId=111&courseId=…">
                <span class="chapterNumber">1.1</span>
                <span class="articlename" title="网络定义">网络定义</span></a>
              <em class="orange">3</em></h3>
              <div class="levelthree"><h3>…</h3></div>
            </div>
          </div>
          <!-- 第一级结束 -->
        </div>

    容器为空（只剩注释）即『老师还没发布章节』，返回 []，不是解析失败。
    """
    soup = node if hasattr(node, "find_all") else BeautifulSoup(str(node), "html.parser")
    root = soup.select_one(".timeline") or soup
    out: list[dict[str, Any]] = []
    unit = ""

    for h3 in root.find_all("h3"):
        # 最近的带 level* 类的祖先决定层级（leveltwo 嵌在 levelone 里，必须取最近的）
        level = 0
        parent = h3.parent
        while parent is not None and parent is not root:
            for cls in parent.get("class") or []:
                if cls in _LEVEL_CLASSES:
                    level = _LEVEL_CLASSES[cls]
                    break
            if level:
                break
            parent = parent.parent

        link = h3.find("a")
        if link is None:
            continue
        name_el = h3.select_one(".articlename")
        name = ""
        if name_el is not None:
            name = (name_el.get("title") or name_el.get_text(" ", strip=True) or "").strip()
        if not name:
            name = link.get_text(" ", strip=True)
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue

        num_el = h3.select_one(".chapterNumber")
        number = num_el.get_text(strip=True) if num_el is not None else ""
        href = (link.get("href") or "").strip()
        if href.startswith(("javascript:", "#")):
            href = ""
        chapter_id = None
        m = re.search(r"chapter[iI]d=(\d+)", href)
        if m:
            chapter_id = int(m.group(1))
        task_el = h3.select_one(".orange, .knowledgeJobCount")
        try:
            task_count = int(task_el.get_text(strip=True)) if task_el is not None else None
        except (TypeError, ValueError):
            task_count = None

        if not level:
            level = 2  # 容器类名缺失时按章节处理，不至于把整棵树丢掉

        if level == 1:
            unit = name
        out.append(
            {
                "title": f"{number} {name}".strip()[:120],
                "level": level,
                "unit": unit,
                "chapterId": chapter_id,
                "url": urljoin(base_url, href) if href else "",
                "taskCount": task_count,
            }
        )
    return out


def list_chapters(sess: ChaoxingSession, course: dict[str, Any]) -> list[dict[str, Any]]:
    """解析章节树。

    2026-09 实机校准：章节**是服务端渲染**在课程主页（stucoursemiddle 会 302 到
    `/mooc-ans/mycourse/studentcourse`）的 `<div class="timeline">` 容器里的，
    并不依赖前端 JS 二次拉取。此前"章节由 JS 动态加载、纯 HTTP 拿不到"的结论是错的——
    真实情况是该容器为空（`<!-- 第一级开始 --><!-- 第一级结束 -->`），
    即老师尚未发布章节，应当返回空列表而不是报错。
    """
    # 形态 0（新版实机）：课程主页内嵌 .timeline 章节树
    try:
        home = sess.get(course_home_url(course))
        soup = BeautifulSoup(home.text, "html.parser")
        timeline = soup.select_one(".timeline")
        if timeline is not None:
            chapters = parse_chapter_tree(timeline, str(home.url))
            if chapters:
                return chapters
            # 容器存在但一行都没有 → 该课程尚未发布章节，属正常空状态
            return []
    except Exception as exc:  # noqa: BLE001 - 形态 0 失败则回退菜单查找
        log.debug("课程主页章节树获取失败，回退菜单方式: %s", exc)

    last_err: Exception | None = None
    for keyword in ("章节", "目录", "任务", "学习"):
        try:
            url = find_menu_url(sess, course, keyword)
        except UpstreamChanged as e:
            last_err = e
            continue
        resp = sess.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        chapters: list[dict[str, Any]] = []

        # 形态 A: 章节标题容器
        for node in soup.select(".chapterText, .prev_ul li, .clearfix.chapter, .chapterUnit"):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            link = node.find("a", href=True) or node.find("a")
            href = ""
            if link is not None:
                href = link.get("data") or link.get("href") or ""
            chapters.append({"title": re.sub(r"\s+", " ", text)[:120], "url": href})

        # 形态 B: 脚本内 chapterList JSON
        if not chapters:
            m = re.search(r"chapterList\s*=\s*(\[.*?\]);", resp.text, re.S)
            if m:
                import json

                try:
                    raw = json.loads(m.group(1))
                    for ch in raw:
                        if isinstance(ch, dict):
                            chapters.append(
                                {
                                    "title": str(ch.get("name") or ch.get("title") or ""),
                                    "id": ch.get("id"),
                                    "url": str(ch.get("url") or ""),
                                }
                            )
                except json.JSONDecodeError:
                    pass

        if chapters:
            return chapters

    raise UpstreamChanged(
        "章节树解析失败：课程主页没有 .timeline 容器，且菜单里的章节页也未渲染出章节行。"
        "可能该课程把『章节/目录』菜单隐藏了，或模板再次改版——"
        "请在浏览器 F12 里确认章节列表的来源（页面内嵌 or XHR），再扩展 api/chapters.py。"
        f"（最后一次菜单查找错误: {last_err}）"
    )
