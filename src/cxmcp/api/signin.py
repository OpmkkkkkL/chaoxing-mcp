"""班级活动与签到。

教师发起签到、学生签到端点在社区项目（chaoxingsign / CxKitty）中随年份
多次变动，这里采用「候选端点探测」：依次尝试已知形态，全部失败时返回
结构化探测记录，供实机抓包校准，而不是瞎猜一个写死的 URL。
"""

from __future__ import annotations

import time
from typing import Any

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession

MOOC1 = "https://mooc1.chaoxing.com"
MOOC1_API = "https://mooc1-api.chaoxing.com"

SIGNIN_TYPES = {
    "normal": "普通签到（一键）",
    "gesture": "手势签到（需图案参数，暂只支持查询）",
    "location": "位置签到（经纬度+地址）",
    "code": "签到码签到（4 位数字）",
    "photo": "拍照签到（本地图片路径）",
}


def _probe_candidates(
    sess: ChaoxingSession, urls: list[str], label: str
) -> dict[str, Any]:
    tried: list[dict[str, str]] = []
    for url in urls:
        try:
            resp = sess.get(url, allow_redirects=True)
            ok = resp.status_code == 200 and "error" not in resp.url
            tried.append({"url": url, "status": str(resp.status_code), "ok": str(ok)})
            if ok and len(resp.text) > 500:
                return {"url": url, "html": resp.text, "tried": tried}
        except Exception as exc:  # noqa: BLE001
            tried.append({"url": url, "status": f"error: {exc}", "ok": "False"})
    raise UpstreamChanged(
        f"{label} 的候选端点全部探测失败，需实机抓包校准。探测记录: "
        + " | ".join(t["url"] + " -> " + t["status"] for t in tried)
    )


# ------------------------------------------------------------------ 教师
def create_signin(
    sess: ChaoxingSession,
    course: dict[str, Any],
    signin_type: str,
    location: str | None = None,
    code: str | None = None,
    duration_minutes: int = 10,
) -> dict[str, Any]:
    """发起签到活动（高影响操作，需确认门）。"""
    if signin_type not in SIGNIN_TYPES:
        raise UpstreamChanged(f"未知签到类型 {signin_type}，支持: {list(SIGNIN_TYPES)}")
    payload: dict[str, Any] = {
        "courseId": course["courseId"],
        "clazzId": course["clazzId"],
        "cpi": course.get("cpi"),
        "name": f"签到-{time.strftime('%H:%M')}",
        "startTime": int(time.time() * 1000),
        "endTime": int((time.time() + duration_minutes * 60) * 1000),
        "type": signin_type,
    }
    if signin_type == "location" and location:
        payload["location"] = location
    if signin_type == "code":
        if not code or not code.isdigit() or len(code) != 4:
            raise UpstreamChanged("签到码必须是 4 位数字")
        payload["signCode"] = code
    probe = _probe_candidates(
        sess,
        [
            f"{MOOC1_API}/work/activecard/create?{''}",
            f"{MOOC1}/attendance/create",
        ],
        "发起签到",
    )
    resp = sess.post(probe["url"], data=payload)
    return {"httpStatus": resp.status_code, "response": resp.text[:400], "payload": payload}


def get_signin_status(sess: ChaoxingSession, course: dict[str, Any]) -> dict[str, Any]:
    probe = _probe_candidates(
        sess,
        [
            f"{MOOC1_API}/work/activecard/list?courseId={course['courseId']}&clazzId={course['clazzId']}",
            f"{MOOC1}/attendance/list?courseId={course['courseId']}",
        ],
        "签到活动列表",
    )
    return {"url": probe["url"], "html": probe["html"][:2000]}


# ------------------------------------------------------------------ 学生
def sign_in(
    sess: ChaoxingSession,
    activity_id: str,
    signin_type: str,
    uid: str | None = None,
    longitude: str | None = None,
    latitude: str | None = None,
    address: str | None = None,
    code: str | None = None,
    photo_path: str | None = None,
) -> dict[str, Any]:
    """学生签到。activity_id 来自活动列表（cx_s_list_activities）。

    注意：仅支持「本人在场」的正常签到；伪造位置/代签不在支持范围内。
    """
    data: dict[str, Any] = {
        "activeId": activity_id,
        "type": signin_type,
        "uid": uid or sess.uid,
        "_t": int(time.time() * 1000),
    }
    if signin_type == "location":
        data.update(
            {
                "longitude": longitude or "",
                "latitude": latitude or "",
                "address": address or "",
            }
        )
    if signin_type == "code":
        if not code or not code.isdigit() or len(code) != 4:
            raise UpstreamChanged("签到码必须是 4 位数字")
        data["signCode"] = code
    if signin_type == "photo":
        from pathlib import Path

        if not photo_path or not Path(photo_path).exists():
            raise UpstreamChanged("拍照签到需要有效的本地图片路径")
        probe = _probe_candidates(
            sess, [f"{MOOC1}/attendance/uploadPhoto", f"{MOOC1_API}/attendance/uploadPhoto"], "照片上传"
        )
        with open(photo_path, "rb") as f:
            resp = sess.post(probe["url"], files={"photo": f}, data=data)
        return {"httpStatus": resp.status_code, "response": resp.text[:300]}

    probe = _probe_candidates(
        sess,
        [
            f"{MOOC1_API}/attendance/{signin_type}Sign",
            f"{MOOC1}/attendance/{signin_type}Sign",
        ],
        f"{signin_type} 签到",
    )
    resp = sess.post(probe["url"], data=data)
    return {"httpStatus": resp.status_code, "response": resp.text[:300], "type": signin_type}


def list_activities(sess: ChaoxingSession, course: dict[str, Any]) -> dict[str, Any]:
    probe = _probe_candidates(
        sess,
        [
            f"{MOOC1_API}/work/mobileClassActivity/list?courseId={course['courseId']}&clazzId={course['clazzId']}",
            f"{MOOC1}/attendance/activeList?courseId={course['courseId']}",
        ],
        "班级活动列表",
    )
    return {"url": probe["url"], "html": probe["html"][:2000]}
