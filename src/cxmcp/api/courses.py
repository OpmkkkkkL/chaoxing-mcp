"""课程列表与课程定位。

学生端"我学的课"与教师端课程均可用 backclazzdata 拉取（教师身份下同一
接口返回其任教课程）。返回结构较深，这里做防御性解析并透出原始角色字段。
"""

from __future__ import annotations

from typing import Any

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession, MOOC1_API

COURSE_KEYS = ("name", "courseId", "clazzId", "cpi", "puid", "teacher", "roleId")


def _as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _first_teacher(course: dict[str, Any]) -> str:
    teachers = course.get("teacherList") or []
    if isinstance(teachers, list):
        names = []
        for t in teachers:
            if isinstance(t, dict) and t.get("name"):
                names.append(str(t["name"]))
        return ", ".join(names)
    if isinstance(course.get("teacher"), str):
        return course["teacher"]
    return ""


def list_courses(sess: ChaoxingSession) -> list[dict[str, Any]]:
    """拉取课程列表（含 courseId / clazzId / cpi，后续接口都要用）。"""
    data = sess.get_json(f"{MOOC1_API}/mycourse/backclazzdata")
    channels = data.get("channelList") if isinstance(data, dict) else None
    if not isinstance(channels, list):
        raise UpstreamChanged("backclazzdata 返回缺少 channelList")

    courses: list[dict[str, Any]] = []
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        content = ch.get("content")
        if not isinstance(content, dict):
            continue
        course_obj = content.get("course")
        course = {}
        if isinstance(course_obj, dict):
            data_list = course_obj.get("data")
            if isinstance(data_list, list) and data_list and isinstance(data_list[0], dict):
                course = data_list[0]
        course_id = _as_int(course.get("id")) or _as_int(content.get("courseId"))
        if course_id is None:
            continue
        courses.append(
            {
                "name": course.get("name") or content.get("courseName") or "",
                "courseId": course_id,
                "clazzId": _as_int(content.get("id")) or _as_int(content.get("clazzId")),
                "cpi": _as_int(content.get("cpi")),
                "puid": _as_int(ch.get("puid")),
                "teacher": _first_teacher(course),
                "roleId": _as_int(ch.get("roleId")),
            }
        )
    return courses


def resolve_course(
    courses: list[dict[str, Any]], ref: str
) -> dict[str, Any]:
    """按名称模糊匹配或按 courseId 精确匹配。"""
    if not courses:
        raise UpstreamChanged("课程列表为空")
    ref_s = str(ref).strip()
    for c in courses:
        if str(c.get("courseId")) == ref_s:
            return c
    matches = [c for c in courses if ref_s in str(c.get("name", ""))]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise UpstreamChanged(
            f"课程名『{ref}』匹配到 {len(matches)} 门课，请改用 courseId 精确指定: "
            + "; ".join(f"{m['name']}({m['courseId']})" for m in matches)
        )
    raise UpstreamChanged(f"未找到课程『{ref}』，可用 courseId 重试")
