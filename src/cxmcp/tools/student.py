"""学生端工具集（11 个）。提交作业走确认门，暂存不需要。"""

from __future__ import annotations

from typing import Any

from ..api import chapters as chapters_api
from ..api import exams as exams_api
from ..api import files as files_api
from ..api import signin as signin_api
from ..api import work as work_api
from .common import AppContext, confirmed, require_course, require_login, safe_tool


def register_student(mcp: Any, ctx: AppContext) -> None:

    @mcp.tool(
        name="cx_s_list_learning_courses",
        description="列出『我学的课』（courseId/clazzId/cpi/教师名），后续操作用这些 ID 定位。",
    )
    @safe_tool
    def cx_s_list_learning_courses() -> dict[str, Any]:
        require_login(ctx)
        from ..api import courses as courses_api

        items = courses_api.list_courses(ctx.session)
        return {"count": len(items), "courses": items}

    @mcp.tool(name="cx_s_list_chapters", description="列出课程章节树（章节名/链接）。")
    @safe_tool
    def cx_s_list_chapters(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        items = chapters_api.list_chapters(ctx.session, course)
        return {"count": len(items), "chapters": items}

    @mcp.tool(name="cx_s_list_homeworks", description="列出课程作业（标题/状态/时间/详情链接）。")
    @safe_tool
    def cx_s_list_homeworks(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        items = work_api.list_homeworks(ctx.session, course)
        return {"count": len(items), "homeworks": items}

    @mcp.tool(
        name="cx_s_get_homework_detail",
        description=(
            "读取作业详情：题目列表（题干/选项/题型）、附件列表、standardEnc。"
            "不会自动作答或提交。"
        ),
    )
    @safe_tool
    def cx_s_get_homework_detail(courseRef: str, workUrl: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        return work_api.get_homework_detail(ctx.session, course, workUrl)

    @mcp.tool(name="cx_s_download_attachment", description="下载作业/资料附件到本地（objectId 定位）。")
    @safe_tool
    def cx_s_download_attachment(objectId: str, saveDir: str) -> dict[str, Any]:
        require_login(ctx)
        return work_api.download_attachment(ctx.session, objectId, saveDir)

    @mcp.tool(name="cx_s_list_exams", description="列出课程考试（标题/状态/入口链接）。只读取，不进入答题。")
    @safe_tool
    def cx_s_list_exams(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        items = exams_api.list_exams(ctx.session, course)
        return {"count": len(items), "exams": items}

    @mcp.tool(name="cx_s_list_materials", description="列出课程『资料』目录的文件（名称/objectId）。")
    @safe_tool
    def cx_s_list_materials(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        items = files_api.list_materials(ctx.session, course)
        return {"count": len(items), "materials": items}

    @mcp.tool(name="cx_s_download_material", description="按 objectId 下载课程资料（getYunFiles 直链优先）。")
    @safe_tool
    def cx_s_download_material(objectId: str, saveDir: str) -> dict[str, Any]:
        require_login(ctx)
        return files_api.download_material(ctx.session, objectId, saveDir)

    @mcp.tool(name="cx_s_get_study_records", description="查看课程学习记录（菜单『学习记录/统计』页解析）。")
    @safe_tool
    def cx_s_get_study_records(courseRef: str) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        from ..api.chapters import find_menu_url

        try:
            url = find_menu_url(ctx.session, course, "记录")
        except Exception:  # noqa: BLE001
            url = find_menu_url(ctx.session, course, "统计")
        resp = ctx.session.get(url)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = [
            [td.get_text(" ", strip=True) for td in tr.find_all("td")][:8]
            for tr in soup.select("table tbody tr")
        ]
        rows = [r for r in rows if r]
        return {"url": url, "count": len(rows), "rows": rows}

    @mcp.tool(
        name="cx_s_sign_in",
        description="学生签到：normal（一键）/location（位置）/code（签到码）/photo（拍照）。",
    )
    @safe_tool
    def cx_s_sign_in(
        activityId: str,
        signinType: str = "normal",
        longitude: str | None = None,
        latitude: str | None = None,
        address: str | None = None,
        code: str | None = None,
        photoPath: str | None = None,
    ) -> dict[str, Any]:
        require_login(ctx)
        if signinType == "photo" and photoPath:
            confirmed(
                ctx,
                "cx_s_sign_in",
                {"activityId": activityId, "signinType": signinType, "photoPath": photoPath},
                f"将上传照片 {photoPath} 用于签到 {activityId}",
                None,  # 照片上传属于个人信息操作，必须确认
            )
        return signin_api.sign_in(
            ctx.session,
            activity_id=activityId,
            signin_type=signinType,
            longitude=longitude,
            latitude=latitude,
            address=address,
            code=code,
            photo_path=photoPath,
        )

    @mcp.tool(
        name="cx_s_submit_homework",
        description=(
            "作业作答：submit=false 为暂存（安全）；submit=true 为正式提交（★高影响，"
            "首次调用返回 confirmToken，确认后携带 token + 同参数重调）。"
            "answers 格式: [{\"stem\":\"题干关键词\",\"answer\":\"A\"}]。"
        ),
    )
    @safe_tool
    def cx_s_submit_homework(
        courseRef: str,
        workUrl: str,
        answers: list[dict[str, Any]],
        submit: bool = False,
        confirmToken: str | None = None,
    ) -> dict[str, Any]:
        course = require_course(ctx, courseRef)
        detail = work_api.get_homework_detail(ctx.session, course, workUrl)
        if submit:
            confirmed(
                ctx,
                "cx_s_submit_homework",
                {"courseId": course["courseId"], "workUrl": workUrl,
                 "answerCount": len(answers), "submit": True},
                f"将正式提交作业（{detail.get('questionCount')} 题），提交后可能无法修改",
                confirmToken,
            )
        return work_api.save_or_submit(ctx.session, detail, answers, submit=submit, confirm_token=confirmToken)
