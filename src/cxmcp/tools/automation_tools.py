"""自动化工具（默认关闭）。

⚠️ 风险声明：视频任务点模拟与 AI 答题属逆向协议使用，可能违反平台条款与
所在院校学术规范，后果自负。仅当 student server 以 --enable-automation
启动时才注册这组工具。
"""

from __future__ import annotations

from typing import Any

from ..api import automation as auto_api
from .common import AppContext, confirmed, require_course, require_login, safe_tool

RISK_NOTE = "自动化协议未经大规模实机验证，且存在学术诚信与账号风险"


def register_automation(mcp: Any, ctx: AppContext) -> None:

    @mcp.tool(
        name="cx_s_simulate_video_task",
        description=(
            f"★【实验性】模拟视频任务点播放心跳（不拉流，按间隔上报进度直至时长）。"
            f"{RISK_NOTE}。★ 高影响操作：首次调用返回 confirmToken。"
            "fileId/objectId 可从章节任务点页面获取。"
        ),
    )
    @safe_tool
    def cx_s_simulate_video_task(
        courseRef: str,
        fileId: str,
        objectId: str,
        durationSeconds: int,
        speed: int = 1,
        confirmToken: str | None = None,
    ) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        confirmed(
            ctx,
            "cx_s_simulate_video_task",
            {"courseId": course["courseId"], "fileId": fileId, "objectId": objectId,
             "durationSeconds": durationSeconds, "speed": speed},
            f"将模拟课程『{course['name']}』视频任务点 {objectId} 的播放心跳",
            confirmToken,
        )
        require_login(ctx)
        return auto_api.simulate_video_heartbeat(
            ctx.session, course, fileId, objectId, durationSeconds, speed
        )

    @mcp.tool(
        name="cx_s_auto_answer_quiz",
        description=(
            f"★【实验性】章节测验 AI 答题。两段式：不传 answers 时返回题目列表"
            f"（由宿主大模型作答）；传入 answers 且携带 confirmToken 时提交。"
            f"{RISK_NOTE}。★ 提交为高影响操作，必须走确认门。"
        ),
    )
    @safe_tool
    def cx_s_auto_answer_quiz(
        courseRef: str,
        quizUrl: str,
        answers: list[dict[str, Any]] | None = None,
        confirmToken: str | None = None,
    ) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        require_login(ctx)
        if not answers:
            questions = auto_api.fetch_quiz_questions(ctx.session, course, quizUrl)
            return {
                "stage": "questions_fetched",
                "count": len(questions),
                "questions": questions,
                "next": "让宿主 LLM 作答后，携带 answers + confirmToken 再次调用本工具提交",
            }
        confirmed(
            ctx,
            "cx_s_auto_answer_quiz",
            {"courseId": course["courseId"], "quizUrl": quizUrl, "answerCount": len(answers)},
            f"将向章节测验提交 {len(answers)} 个 AI 生成的答案",
            confirmToken,
        )
        return auto_api.submit_quiz_answers(ctx.session, course, quizUrl, answers)
