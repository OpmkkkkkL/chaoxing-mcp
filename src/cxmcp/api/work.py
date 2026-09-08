"""作业 API（教师批改视图 + 学生答题视图共用的抓取逻辑）。

关键逆向结论：
- 作业列表: 课程菜单里的 /work/getAllWork?...（相对 mooc1-2）；
- 作业详情 enc 有两个：页面级 &enc= 与作业级 enc（藏在 $(".inspectTask").click
  脚本里）。请求详情必须用 mooc-ans/work/isExpire 返回的 standardEnc，
  用错页面级 enc 会 403；
- 附件: mooc-ans/ueditorupload/read?objectId=... 解析 btnDown 真实地址
  （class/href 顺序有两种写法，双正则兜底）。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession

MOOC1_2 = "https://mooc1-2.chaoxing.com"
MOOC_ANS = "https://mooc1.chaoxing.com/mooc-ans"


# ------------------------------------------------------------------ 列表
def list_homeworks(sess: ChaoxingSession, course: dict[str, Any]) -> list[dict[str, Any]]:
    """解析作业列表（2026-09 实测模板：li.lookLi + a.removeReddot + .titTxt）。

    实机结构：
    - 每个作业是 <li class="lookLi">；
    - 标题链接 <a class="removeReddot" title="完整作业名"
      href="/mooc-ans/work/viewWork?id=...&courseId=...&classId=...&workId=...&enc=...">，
      href 即查看入口且自带作业级 enc；
    - .titTxt 文本含 开始时间/截止时间/作业状态。
    """
    from .chapters import find_menu_url

    menu_url = find_menu_url(sess, course, "作业")
    resp = sess.get(menu_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    rows: list[dict[str, Any]] = []

    for li in soup.select("li.lookLi"):
        link = li.select_one("a.removeReddot") or li.find("a", href=True)
        title = (link.get("title") or link.get_text(" ", strip=True)) if link else ""
        if not title:
            continue
        href = urljoin(str(resp.url), link["href"]) if link and link.get("href") else ""
        text = li.get_text(" ", strip=True)
        status = (re.search(r"作业状态[：:]\s*([^ \t]+)", text) or [None, ""])[1]
        deadline = (re.search(r"截止时间[：:]\s*([0-9\-: ]+)", text) or [None, ""])[1].strip()
        rows.append(
            {
                "title": title[:150],
                "status": status,
                "deadline": deadline,
                "workId": link.get("data") if link else None,
                "url": href,
                **_course_ids(course),
            }
        )

    if not rows:  # 兼容旧表格模板
        for table in soup.select("table"):
            for tr in table.select("tbody tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if not cells or len(cells) < 2:
                    continue
                link = tr.find("a", href=True)
                title = (link.get_text(strip=True) if link else "") or cells[0]
                if title in ("", "操作", "标题"):
                    continue
                rows.append(
                    {
                        "title": title[:150],
                        "status": "",
                        "deadline": "",
                        "url": urljoin(str(resp.url), link["href"]) if link else "",
                        "workId": None,
                        **_course_ids(course),
                    }
                )
    if not rows:
        raise UpstreamChanged("作业列表页解析为空（模板可能改版）")
    return rows


def _course_ids(course: dict[str, Any]) -> dict[str, Any]:
    return {"courseId": course["courseId"], "clazzId": course["clazzId"], "cpi": course.get("cpi")}


# ------------------------------------------------------------------ enc
def get_standard_enc(
    sess: ChaoxingSession, course: dict[str, Any], work_url: str
) -> tuple[str, dict[str, Any]]:
    """从作业 URL 提取 workRelationId/workId，请求 isExpire 拿 standardEnc。

    返回 (enc, ids)；ids 含 workRelationId/classId/courseId 供提交表单复用。
    """
    from urllib.parse import parse_qs, urlparse

    q = parse_qs(urlparse(work_url).query)
    work_relation_id = (q.get("workRelationId") or q.get("workId") or [""])[0]
    class_id = (q.get("classId") or q.get("clazzid") or [str(course["clazzId"])])[0]
    course_id = (q.get("courseId") or q.get("courseid") or [str(course["courseId"])])[0]
    if not work_relation_id:
        raise UpstreamChanged(f"作业 URL 中未找到 workRelationId: {work_url}")
    api = (
        f"{MOOC_ANS}/work/isExpire?classId={class_id}&workRelationId={work_relation_id}"
        f"&cpi={course.get('cpi') or 0}&courseId={course_id}"
    )
    data = sess.get_json(api)
    enc = data.get("data", {}).get("standardEnc") if isinstance(data.get("data"), dict) else None
    if not enc:
        enc = data.get("standardEnc")
    if not enc:
        raise UpstreamChanged(f"isExpire 未返回 standardEnc: {str(data)[:200]}")
    return str(enc), {"workRelationId": work_relation_id, "classId": class_id, "courseId": course_id}


def build_detail_url(work_url: str, enc: str) -> str:
    """拼 doHomeWorkNew 详情页地址。"""
    base = work_url.split("?")[0]
    sep = "&" if "?" in work_url else "?"
    if "doHomeWorkNew" in work_url or "doHomeWork" in work_url:
        return f"{work_url}{sep}enc={enc}"
    return f"{MOOC_ANS}/work/doHomeWorkNew{sep}enc={enc}"


# ------------------------------------------------------------------ 详情
def get_homework_detail(
    sess: ChaoxingSession, course: dict[str, Any], work_url: str
) -> dict[str, Any]:
    m = re.search(r"enc=([a-z0-9]{32})", work_url)
    if m:
        enc = m.group(1)
        ids: dict[str, Any] = _course_ids(course)
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(work_url).query)
        ids["workRelationId"] = (q.get("workRelationId") or q.get("workId") or [""])[0]
    else:
        enc, ids = get_standard_enc(sess, course, work_url)
    detail_url = build_detail_url(work_url, enc)
    resp = sess.get(detail_url)
    if resp.status_code == 403:
        raise UpstreamChanged("作业详情 403：enc 可能不匹配（需要 standardEnc）")
    soup = BeautifulSoup(resp.text, "html.parser")
    questions: list[dict[str, Any]] = []
    # 优先 div.TiMu（官方模板），避免 .Zy_TItle 等子节点重复计数
    blocks = soup.select("div.TiMu") or soup.select(".questionLi") or soup.select(".Zy_TItle")
    for q in blocks:
        stem_el = q.select_one(".Zy_TItle, .qtContent, .Cy_TItle, .stem") or q
        stem = stem_el.get_text(" ", strip=True)[:500]
        options = [opt.get_text(" ", strip=True)[:200] for opt in q.select(".Zy_ulTop li, .uls li, .options li")]
        qtype = "unknown"
        if "单选" in stem:
            qtype = "single"
        elif "多选" in stem:
            qtype = "multiple"
        elif "判断" in stem:
            qtype = "judge"
        elif "填空" in stem:
            qtype = "blank"
        questions.append({"stem": stem, "options": options, "type": qtype})
    attachments = []
    for iframe in soup.select("iframe[objectid]"):
        attachments.append(
            {"objectId": iframe.get("objectid"), "filename": iframe.get("filename") or ""}
        )
    return {
        "enc": enc,
        "detailUrl": detail_url,
        "questionCount": len(questions),
        "questions": questions,
        "attachments": attachments,
        **ids,
    }


# ------------------------------------------------------------------ 提交/暂存（学生）
def save_or_submit(
    sess: ChaoxingSession,
    detail: dict[str, Any],
    answers: list[dict[str, Any]],
    submit: bool,
    confirm_token: str | None,
) -> dict[str, Any]:
    """答题暂存 / 提交。

    answers: [{"stem": 题干前缀, "answer": "A"}...]，按顺序匹配题目。
    提交为高影响操作，必须先走确认门（由 tools 层负责）。
    端点参数随课程模板变化，首次实机使用建议先暂存回读核对。
    """
    import json as _json

    form: dict[str, Any] = {
        "enc": detail.get("enc", ""),
        "courseId": detail.get("courseId"),
        "classId": detail.get("classId"),
        "workRelationId": detail.get("workRelationId", ""),
    }
    for idx, q in enumerate(detail.get("questions", [])):
        matched = next((a for a in answers if a.get("stem") and a["stem"] in q["stem"]), None)
        form[f"answer{idx}"] = matched["answer"] if matched else ""
    form["submit"] = "true" if submit else "false"
    url = detail.get("detailUrl", "")
    resp = sess.post(url.replace("doHomeWorkNew", "work/addStudentWorkNew"), data=form)
    try:
        result = resp.json()
    except ValueError:
        result = {"raw": resp.text[:300]}
    return {"httpStatus": resp.status_code, "result": result, "form": _json.dumps(form, ensure_ascii=False)[:500]}


# ------------------------------------------------------------------ 附件
def download_attachment(
    sess: ChaoxingSession, object_id: str, save_dir: str
) -> dict[str, Any]:
    """通过 ueditorupload/read 解析真实下载地址并落盘。"""
    from pathlib import Path

    page = sess.get(f"{MOOC_ANS}/ueditorupload/read", params={"objectId": object_id})
    soup = BeautifulSoup(page.text, "html.parser")
    href = None
    node = soup.find("a", class_=re.compile(r"btnDown"))
    if node is not None and node.get("href"):
        href = node["href"]
    if not href:
        m = re.search(r'href="([^"]+)"[^>]*class="[^"]*btnDown', page.text) or re.search(
            r'class="[^"]*btnDown[^"]*"[^>]*href="([^"]+)"', page.text
        )
        href = m.group(1) if m else None
    if not href:
        raise UpstreamChanged("附件页未解析到 btnDown 下载地址")
    real = urljoin(str(page.url), href)
    binary = sess.get(real)
    out_dir = Path(save_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = binary.headers.get("Content-Disposition", "")
    m2 = re.search(r'filename="?([^";]+)"?', name)
    filename = m2.group(1) if m2 else f"{object_id}.bin"
    out_path = out_dir / filename
    out_path.write_bytes(binary.content)
    return {"path": str(out_path), "size": len(binary.content), "url": real}
