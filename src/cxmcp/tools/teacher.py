"""教师端工具集（12 个）。带 ★ 的为高影响操作，走两阶段确认。"""

from __future__ import annotations

from typing import Any

from ..api import chapters as chapters_api
from ..api import signin as signin_api
from ..api import teacher as teacher_api
from ..api import work as work_api
from .common import AppContext, confirmed, require_course, safe_tool, require_login


def register_teacher(mcp: Any, ctx: AppContext) -> None:

    @mcp.tool(
        name="cx_t_list_classes",
        description="列出『我教的课』及班级信息（courseId/clazzId/cpi/教师名）。",
    )
    @safe_tool
    def cx_t_list_classes() -> dict[str, Any]:
        require_login(ctx)
        from ..api import courses as courses_api

        items = courses_api.list_courses(ctx.session)
        return {"count": len(items), "courses": items}

    @mcp.tool(name="cx_t_list_chapters", description="列出课程章节树。courseRef 为课程名或 courseId。")
    @safe_tool
    def cx_t_list_chapters(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        items = chapters_api.list_chapters(ctx.session, course)
        return {"count": len(items), "chapters": items}

    @mcp.tool(
        name="cx_t_get_chapter_detail",
        description="抓取章节/任意课程页 URL 的原始内容摘要（调试与内容核对用）。",
    )
    @safe_tool
    def cx_t_get_chapter_detail(courseRef: str, chapterUrl: str) -> dict[str, Any]:
        require_course(ctx, courseRef)
        resp = ctx.session.get(chapterUrl)
        return {"url": str(resp.url), "length": len(resp.text), "excerpt": resp.text[:1500]}

    @mcp.tool(name="cx_t_list_homeworks", description="列出课程作业（名称/状态/时间/详情链接）。")
    @safe_tool
    def cx_t_list_homeworks(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        items = work_api.list_homeworks(ctx.session, course)
        return {"count": len(items), "homeworks": items}

    @mcp.tool(
        name="cx_t_get_homework_submissions",
        description="查看某份作业的学生提交列表（从作业 URL 进入批改页解析）。",
    )
    @safe_tool
    def cx_t_get_homework_submissions(courseRef: str, workUrl: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        resp = ctx.session.get(workUrl)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        submissions = []
        for tr in soup.select("table tbody tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            link = tr.find("a", href=True)
            if cells:
                submissions.append({"cells": cells[:8], "url": link["href"] if link else ""})
        return {"count": len(submissions), "submissions": submissions}

    @mcp.tool(
        name="cx_t_download_submission",
        description="下载学生提交的附件到本地目录（解析 ueditorupload read 页）。",
    )
    @safe_tool
    def cx_t_download_submission(objectId: str, saveDir: str) -> dict[str, Any]:
        require_login(ctx)
        return work_api.download_attachment(ctx.session, objectId, saveDir)

    @mcp.tool(
        name="cx_t_review_homework",
        description=(
            "★批改学生作业（打分+评语）。★ 高影响操作：首次调用返回 confirmToken，"
            "向用户复述 [课程/学生/分数/评语] 获得明确同意后，携带 token 原样重调。"
        ),
    )
    @safe_tool
    def cx_t_review_homework(
        submissionUrl: str, score: float, comment: str = "", confirmToken: str | None = None
    ) -> dict[str, Any]:
        confirmed(
            ctx,
            "cx_t_review_homework",
            {"submissionUrl": submissionUrl, "score": score, "comment": comment},
            f"将给学生作业打分 {score} 分并提交评语",
            confirmToken,
        )
        require_login(ctx)
        return teacher_api.review_homework(ctx.session, submissionUrl, score, comment)

    @mcp.tool(name="cx_t_get_gradebook", description="查看课程成绩册（解析成绩页表格）。")
    @safe_tool
    def cx_t_get_gradebook(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        return teacher_api.get_gradebook(ctx.session, course)

    @mcp.tool(
        name="cx_t_create_signin",
        description=(
            "★发起班级签到（normal/location/code/photo，可设时长）。★ 高影响操作："
            "首次调用返回 confirmToken，确认后携带 token 重调。端点需实机校准，"
            "失败会返回探测记录。"
        ),
    )
    @safe_tool
    def cx_t_create_signin(
        courseRef: str,
        signinType: str = "normal",
        location: str | None = None,
        code: str | None = None,
        durationMinutes: int = 10,
        confirmToken: str | None = None,
    ) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        confirmed(
            ctx,
            "cx_t_create_signin",
            {"courseId": course["courseId"], "clazzId": course["clazzId"], "signinType": signinType,
             "code": code, "location": location, "durationMinutes": durationMinutes},
            f"将在课程『{course['name']}』发起 {signinType} 签到，时长 {durationMinutes} 分钟",
            confirmToken,
        )
        return signin_api.create_signin(ctx.session, course, signinType, location, code, durationMinutes)

    @mcp.tool(name="cx_t_get_signin_status", description="查看课程签到活动列表与状态。")
    @safe_tool
    def cx_t_get_signin_status(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        return signin_api.get_signin_status(ctx.session, course)

    @mcp.tool(
        name="cx_t_send_notice",
        description=(
            "★向班级发送课程通知。★ 高影响操作：首次调用返回 confirmToken，"
            "确认后携带 token 重调。"
        ),
    )
    @safe_tool
    def cx_t_send_notice(
        courseRef: str, title: str, content: str, confirmToken: str | None = None
    ) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        confirmed(
            ctx,
            "cx_t_send_notice",
            {"courseId": course["courseId"], "title": title, "content": content[:100]},
            f"将向课程『{course['name']}』全班发送通知《{title}》",
            confirmToken,
        )
        return teacher_api.send_notice(ctx.session, course, title, content)

    @mcp.tool(
        name="cx_t_upload_material",
        description=(
            "★上传本地文件为课程资料。★ 高影响操作：首次调用返回 confirmToken。"
            "上传端点需实机校准，失败返回探测记录。"
        ),
    )
    @safe_tool
    def cx_t_upload_material(
        courseRef: str, filePath: str, confirmToken: str | None = None
    ) -> dict[str, Any]:
        from pathlib import Path

        course = require_course(ctx, courseRef)
        path = Path(filePath).expanduser()
        if not path.exists():
            return {"ok": False, "errorType": "not_supported", "error": f"文件不存在: {path}"}
        confirmed(
            ctx,
            "cx_t_upload_material",
            {"courseId": course["courseId"], "filePath": str(path)},
            f"将把 {path.name} 上传为课程『{course['name']}』资料",
            confirmToken,
        )
        require_login(ctx)
        resp = ctx.session.post(
            "https://mooc1-2.chaoxing.com/knowledge/uploadFile",
            data={"courseId": course["courseId"], "clazzId": course["clazzId"]},
            files={"file": (path.name, path.read_bytes())},
        )
        return {"httpStatus": resp.status_code, "response": resp.text[:300]}
