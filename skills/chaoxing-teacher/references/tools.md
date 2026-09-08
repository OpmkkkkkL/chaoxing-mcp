# 学习通教师 MCP 工具速查（cx-mcp-teacher）

登录态：`cx_login` / `cx_session_status` / `cx_import_cookies` / `cx_logout`
课程定位：所有业务接口的 `courseRef` 接受 **课程名模糊匹配** 或 **courseId 精确匹配**。

| 工具 | 参数 | 风险 | 说明 |
|---|---|---|---|
| cx_login | username, password | - | 密码仅内存使用，AES-CBC 加密传输 |
| cx_session_status | - | 读 | 回读个人空间判断登录态 |
| cx_list_courses | - | 读 | 通用课程列表（含 clazzId/cpi） |
| cx_import_cookies | cookies[{name,value,domain,path}] | - | 浏览器 Cookie 导入，用于二次验证场景 |
| cx_logout | - | - | 清除本地会话与 Cookie 文件 |
| cx_t_list_classes | - | 读 | 我教的课 + 班级信息 |
| cx_t_list_chapters | courseRef | 读 | 章节树 |
| cx_t_get_chapter_detail | courseRef, chapterUrl | 读 | 章节页原始摘要（核对内容） |
| cx_t_list_homeworks | courseRef | 读 | 作业列表（标题/状态/URL） |
| cx_t_get_homework_submissions | courseRef, workUrl | 读 | 学生提交列表 |
| cx_t_download_submission | objectId, saveDir | 写(本地) | 下载学生附件 |
| cx_t_review_homework ★ | submissionUrl, score, comment, confirmToken? | 高影响 | 批改打分+评语，需两阶段确认 |
| cx_t_get_gradebook | courseRef | 读 | 成绩册表格 |
| cx_t_create_signin ★ | courseRef, signinType, code/location, durationMinutes, confirmToken? | 高影响 | 发起签到；端点需实机校准 |
| cx_t_get_signin_status | courseRef | 读 | 签到活动列表 |
| cx_t_send_notice ★ | courseRef, title, content, confirmToken? | 高影响 | 发班级通知 |
| cx_t_upload_material ★ | courseRef, filePath, confirmToken? | 高影响 | 上传课程资料 |

★ = 两阶段确认：首次调用返回 `confirmation_required` + `confirmToken`（5 分钟有效，一次性，绑定参数指纹），用户明确同意后原参数重调。

## 实机校准说明

`cx_t_create_signin` / `cx_t_upload_material` / `cx_t_send_notice` 的提交端点来自社区逆向，模板随年份变动。失败时返回结构化探测记录（各候选端点状态码），按记录抓包替换 `src/cxmcp/api/` 对应 URL 即可。
