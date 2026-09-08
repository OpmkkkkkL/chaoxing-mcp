"""教师：成绩册 / 通知 / 作业批改提交。

这些端点同样随模板变动，候选端点探测策略与 signin 一致。
"""

from __future__ import annotations

import re
import time
from typing import Any

from bs4 import BeautifulSoup

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession
from .chapters import find_menu_url


# ------------------------------------------------------------------ 成绩
def get_gradebook(sess: ChaoxingSession, course: dict[str, Any]) -> dict[str, Any]:
    url = find_menu_url(sess, course, "成绩")
    resp = sess.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    students: list[dict[str, Any]] = []
    for tr in soup.select("table tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) >= 2:
            students.append({"cells": cells[:8]})
    if not students:
        raise UpstreamChanged("成绩页未解析到数据行")
    return {"students": students, "url": url}


# ------------------------------------------------------------------ 通知
def send_notice(
    sess: ChaoxingSession,
    course: dict[str, Any],
    title: str,
    content: str,
    send_to_all: bool = True,
) -> dict[str, Any]:
    """向班级发通知（高影响操作，需确认门）。"""
    payload = {
        "courseId": course["courseId"],
        "clazzId": course["clazzId"],
        "cpi": course.get("cpi"),
        "title": title,
        "content": content,
        "bSendAll": 1 if send_to_all else 0,
        "sendTime": int(time.time() * 1000),
    }
    tried: list[str] = []
    for url in (
        "https://mooc1-2.chaoxing.com/work/notice/add",
        "https://mooc1-api.chaoxing.com/notice/send",
        "https://mooc2-ans.chaoxing.com/mooc2-ans/notice/save",
    ):
        try:
            resp = sess.post(url, data=payload)
            tried.append(f"{url} -> {resp.status_code}")
            if resp.status_code == 200 and ("success" in resp.text.lower() or "成功" in resp.text):
                return {"sent": True, "url": url, "response": resp.text[:300]}
        except Exception as exc:  # noqa: BLE001
            tried.append(f"{url} -> error: {exc}")
    raise UpstreamChanged("通知发送端点全部探测失败: " + " | ".join(tried))


# ------------------------------------------------------------------ 批改
def review_homework(
    sess: ChaoxingSession,
    submission_url: str,
    score: float,
    comment: str = "",
) -> dict[str, Any]:
    """教师批改学生作业（高影响操作，需确认门）。"""
    from urllib.parse import parse_qs, urlparse

    q = parse_qs(urlparse(submission_url).query)
    payload = {
        "courseId": (q.get("courseId") or [""])[0],
        "classId": (q.get("classId") or q.get("clazzid") or [""])[0],
        "workId": (q.get("workId") or q.get("workRelationId") or [""])[0],
        "userId": (q.get("userId") or q.get("userid") or [""])[0],
        "score": score,
        "comment": comment,
    }
    if not payload["userId"]:
        raise UpstreamChanged(f"批改 URL 缺少 userId: {submission_url}")
    resp = sess.post("https://mooc1-2.chaoxing.com/work/markservice", data=payload)
    body = resp.text[:400]
    ok = resp.status_code == 200 and re.search(r"success|成功", body, re.I)
    return {"sent": bool(ok), "httpStatus": resp.status_code, "response": body, "payload": payload}
