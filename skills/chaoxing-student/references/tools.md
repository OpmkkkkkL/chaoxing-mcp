# 学习通学生 MCP 工具速查（cx-mcp-student）

所有课程接口的 `courseRef` 接受课程名或 courseId；作业相关操作需要 `workUrl`（来自列表返回的 url 字段）。

| 工具 | 参数 | 风险 | 说明 |
|---|---|---|---|
| cx_login | username, password | - | 登录 |
| cx_session_status | - | 读 | 登录态检查 |
| cx_list_courses | - | 读 | 通用课程列表 |
| cx_import_cookies | cookies[...] | - | Cookie 导入 |
| cx_logout | - | - | 退出 |
| cx_s_list_learning_courses | - | 读 | 我学的课 |
| cx_s_list_chapters | courseRef | 读 | 章节树 |
| cx_s_list_homeworks | courseRef | 读 | 作业列表 |
| cx_s_get_homework_detail | courseRef, workUrl | 读 | 题目/附件/enc（不作答） |
| cx_s_download_attachment | objectId, saveDir | 写(本地) | 下载作业附件 |
| cx_s_list_exams | courseRef | 读 | 考试列表（不进入答题） |
| cx_s_list_materials | courseRef | 读 | 资料目录 |
| cx_s_download_material | objectId, saveDir | 写(本地) | 下载资料（getYunFiles 直链） |
| cx_s_get_study_records | courseRef | 读 | 学习记录表格 |
| cx_s_sign_in | activityId, signinType, longitude/latitude/address, code, photoPath | photo 需确认 | 正常签到（普通/位置/签到码/拍照） |
| cx_s_submit_homework ★ | courseRef, workUrl, answers, submit, confirmToken? | submit=true 高影响 | 暂存安全 / 提交需确认 |
| cx_s_simulate_video_task ★（默认关闭） | courseRef, fileId, objectId, durationSeconds, speed | 高影响+诚信风险 | 视频心跳模拟（实验性） |
| cx_s_auto_answer_quiz ★（默认关闭） | courseRef, quizUrl, answers?, confirmToken? | 高影响+诚信风险 | 两段式：先取题 → AI 答 → 确认提交 |

★ = 两阶段确认（5 分钟有效，一次性，绑定参数指纹）。
（默认关闭）= server 需以 `--enable-automation` 启动才注册。

## answers 格式

```json
[{"stem": "题干关键词（用于匹配题目）", "answer": "A"}]
```

先 `submit=false` 暂存 → 用户在学习通页面核对 → 再 `submit=true` 提交。
