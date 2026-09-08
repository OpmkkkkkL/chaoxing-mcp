"""课程主页菜单 + 章节/任务点。

课程主页: https://mooc1-2.chaoxing.com/visit/stucoursemiddle?courseid=&clazzid=&vc=1&cpi=
菜单项: ul.navshow > li > a；很多真实 URL 藏在 <a data="..."> 属性里。
章节: 菜单里的 /knowledge/ 或 /chapter/ 链接，卡片节点页解析章节树。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession

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
def list_chapters(sess: ChaoxingSession, course: dict[str, Any]) -> list[dict[str, Any]]:
    """解析章节树（尽力而为）。

    已知限制（2026-09 实机）：新版课程模板的章节树由 JS 动态加载
    （studentcourse SPA），纯 HTTP 无法直接拿到；此时会返回带指引的错误，
    需要逆向其 AJAX 端点后扩展本函数。
    """
    # 形态 0（2026-09 新版实机）：课程主页(重定向后的 studentcourse 页)
    # 直接内嵌完整章节树，无需等 JS：
    #   <div class="leveltwo"><h3 class="clearfix"><a href='/mooc-ans/mycourse/studentstudy?chapterId=...'>
    #     <span class="chapterNumber">1.1</span><span class="articlename" title="新建目录">新建目录</span>
    try:
        home = sess.get(course_home_url(course))
        tree_soup = BeautifulSoup(home.text, "html.parser")
        chapters = []
        for node in tree_soup.select("div.leveltwo h3.clearfix a[href*='chapterId='], h3.clearfix a[href*='chapterId=']"):
            href = node.get("href") or ""
            num_el = node.select_one(".chapterNumber")
            name_el = node.select_one(".articlename")
            num = num_el.get_text(strip=True) if num_el else ""
            name = (name_el.get("title") or name_el.get_text(" ", strip=True) or "").strip()
            if name:
                url_final = urljoin(str(home.url), href)
                chapters.append({"title": f"{num} {name}".strip()[:120], "url": url_final})
        if chapters:
            return chapters
    except Exception:  # noqa: BLE001 - 形态 0 失败则回退旧逻辑
        pass

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
        "章节树解析失败：新版模板的章节由前端 JS 动态加载，纯 HTTP 拿不到。"
        "可在浏览器 F12 的 Network 面板找到章节列表的 XHR 端点后扩展 api/chapters.py。"
        f"（最后一次菜单查找错误: {last_err}）"
    )
