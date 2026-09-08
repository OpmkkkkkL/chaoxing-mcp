"""自动化模块（默认关闭，--enable-automation / CX_ENABLE_AUTOMATION 显式开启）。

⚠️ 风险声明：本模块实现「视频任务点心跳模拟」与「章节测验 AI 答题」，
   属于对学习通平台自动化协议的逆向使用，可能违反平台条款与所在院校
   学术规范，存在任务异常、课程成绩无效乃至账号处罚的风险。
   开启即代表使用者理解并自行承担全部后果。

协议参考（公开社区项目 CxKitty / Samueli924/chaoxing 的已知行为）：
- 视频心跳: POST multimedia/log/a/{puid}/{fileid}
    参数: clipTime=[0,{duration}], playingTime={秒}, isdrag=0, rt=0.9,
          dtype=Video, otherInfo=..., view=pc
    每 30~58 秒上报一次直到 duration。
- 测验答题: 拉章节测验页解析 div.TiMu -> 组答案 -> addStudentWorkNew 提交。
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..exceptions import UpstreamChanged
from ..session import ChaoxingSession
from .chapters import find_menu_url

MOOC1 = "https://mooc1.chaoxing.com"


def _get_course_meta(sess: ChaoxingSession, course: dict[str, Any]) -> dict[str, Any]:
    """从课程主页 HTML 抽取 puid 等心跳必需参数（缺失则报可校准错误）。"""
    from .chapters import course_home_url

    resp = sess.get(course_home_url(course))
    import re

    m = re.search(r"puid[=\"']+\s*(\d+)", resp.text)
    if not m:
        raise UpstreamChanged("课程主页未找到 puid，心跳协议需要该参数")
    return {"puid": m.group(1)}


def simulate_video_heartbeat(
    sess: ChaoxingSession,
    course: dict[str, Any],
    file_id: str,
    object_id: str,
    duration_seconds: int,
    speed: int = 1,
    max_ticks: int = 200,
    sleep: Callable[[float], None] = time.sleep,
    progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """对单个视频任务点做心跳模拟（不真正拉流，模拟播放进度上报）。

    实验性：端点与参数以社区已知协议为准，实机校准后才可靠。
    speed: 倍速档位（心跳间隔按 30/speed 秒折算）。
    """
    meta = _get_course_meta(sess, course)
    interval = max(1, int(30 / max(speed, 1)))
    playing = 0
    ticks = 0
    url = f"{MOOC1}/multimedia/log/a/{meta['puid']}/{file_id}"
    last_response = ""
    while playing < duration_seconds and ticks < max_ticks:
        playing = min(playing + interval, duration_seconds)
        data = {
            "otherInfo": f"moduleid:{object_id}",
            "clazzId": course["clazzId"],
            "playingTime": playing,
            "duration": duration_seconds,
            "clipTime": f"[0,{duration_seconds}]",
            "objectId": object_id,
            "isdrag": 0,
            "rt": 0.9,
            "dtype": "Video",
            "view": "pc",
            "enc": "",
            "vs": 1,
        }
        resp = sess.post(url, data=data)
        last_response = resp.text[:200]
        ticks += 1
        if progress:
            progress(playing)
        if playing < duration_seconds:
            sleep(interval)
    return {
        "objectId": object_id,
        "reportedPlayingTime": playing,
        "duration": duration_seconds,
        "ticks": ticks,
        "lastResponse": last_response,
        "note": "实验性协议，请核对学习通页面上任务点是否变为已完成",
    }


def fetch_quiz_questions(
    sess: ChaoxingSession, course: dict[str, Any], quiz_url: str
) -> list[dict[str, Any]]:
    """拉取章节测验题目（div.TiMu 结构），返回题干+选项，由宿主 LLM 作答。"""
    resp = sess.get(quiz_url)
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "html.parser")
    questions = []
    for idx, q in enumerate(soup.select("div.TiMu")):
        stem = q.get_text(" ", strip=True)[:500]
        options = [o.get_text(" ", strip=True)[:200] for o in q.select("li, label")]
        qtype = "single"
        if "多选" in stem:
            qtype = "multiple"
        elif "判断" in stem:
            qtype = "judge"
        elif "填空" in stem:
            qtype = "blank"
        questions.append({"index": idx, "type": qtype, "stem": stem, "options": options})
    if not questions:
        raise UpstreamChanged("测验页未解析到 div.TiMu 题目")
    return questions


def submit_quiz_answers(
    sess: ChaoxingSession,
    course: dict[str, Any],
    quiz_url: str,
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    """把 {index, answer} 列表组装为 addStudentWorkNew 表单提交。

    提交为高影响操作，必须走确认门（tools 层处理）。
    """
    from .work import get_homework_detail, save_or_submit

    detail = get_homework_detail(sess, course, quiz_url)
    return save_or_submit(sess, detail, answers, submit=True, confirm_token=None)
