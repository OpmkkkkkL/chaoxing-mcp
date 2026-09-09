"""考试列表（学生视角）。

考试入口在课程菜单『考试』/『作业考试』里，模板多变，这里做候选端点探测。
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession
from .chapters import find_menu_url
from .pagestate import is_empty_page


def list_exams(sess: ChaoxingSession, course: dict[str, Any]) -> list[dict[str, Any]]:
    url = find_menu_url(sess, course, "考试")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    rows: list[dict[str, Any]] = []
    for tr in soup.select("table tbody tr, .exam-list li, .questionLi"):
        text = tr.get_text(" ", strip=True)
        if not text:
            continue
        link = tr.find("a", href=True)
        rows.append(
            {
                "title": text[:150],
                "url": link["href"] if link else "",
                "status": "进行中" if ("进行" in text or "开始" in text) else "",
            }
        )
    if not rows:
        if is_empty_page(soup):
            return rows  # 页面明示『暂无内容』：确实没布置考试
        raise UpstreamChanged("考试列表页解析为空")
    return rows


def get_exam_paper_meta(sess: ChaoxingSession, exam_url: str) -> dict[str, Any]:
    """抓考试页元信息（题量/时长），供用户决定是否进入。不自动开考。"""
    resp = sess.get(exam_url)
    text = resp.text
    meta = {
        "questionCount": None,
        "durationMinutes": None,
        "raw": text[:300],
    }
    m = re.search(r"(\d+)\s*题", text)
    if m:
        meta["questionCount"] = int(m.group(1))
    m = re.search(r"(\d+)\s*分钟", text)
    if m:
        meta["durationMinutes"] = int(m.group(1))
    return meta
