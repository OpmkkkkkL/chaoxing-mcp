---
name: chaoxing-student
description: "学习通学生助手 - 查询超星学习通课程、作业、考试与资料，下载课件附件，暂存/提交作业，正常签到。关键词：学习通、超星、我学的课、作业、考试、资料下载、签到、学习记录"
version: "0.1.0"
author: "cxmcp"
---

# 学习通学生助手

> **目标**：通过 `cx-mcp-student` MCP server 的 `cx_s_*` 系列工具，查询学习课业信息、下载资料、暂存/提交作业。

## 前置条件（每次会话开始时检查）

1. 宿主已配置 `cx-mcp-student` MCP server。未配置时给出下方配置说明。
2. `cx_session_status` 检查登录态；失效时引导 `cx_login`（账号密码）或 `cx_import_cookies`（浏览器导出）。

### MCP 配置说明

```json
{
  "mcpServers": {
    "chaoxing-student": {
      "command": "cx-mcp-student",
      "env": { "CX_COOKIE_FILE": "~/.chaoxing-mcp/student_cookies.json" }
    }
  }
}
```

自动化工具（视频任务点模拟、AI 答题）默认关闭，需以 `cx-mcp-student --enable-automation` 启动。

## When to Use

用户以**学生身份**提及学习通/超星：我的课、未完成作业、考试安排、下载课件资料、学习记录、正常签到、暂存/提交作业。

## When NOT to Use（重要）

- 用户意图是**教师**管理操作（批改、发通知、发起签到）→ 使用 `chaoxing-teacher` skill。
- 用户要求**代签到、伪造位置签到、绕过人脸/验证码** → 拒绝。
- 用户要求**替同学答题、批量刷课牟利** → 拒绝。

## 操作确认协议（强制，最高优先级）

| 工具 | 确认要求 |
|---|---|
| `cx_s_submit_homework` submit=true | ★ 必须确认：复述课程、作业名、题数，说明"提交后可能无法修改" |
| `cx_s_submit_homework` submit=false | 暂存，无需确认 |
| `cx_s_sign_in` photo | ★ 上传照片属于个人信息操作，必须确认 |
| `cx_s_sign_in` 其他类型 | 无需确认（本人在场的正常签到） |
| 自动化工具（若启用） | ★ 必须确认 + 口头提示学术诚信风险 |

流程：首次调用返回 `confirmation_required` + `confirmToken` → 向用户复述影响 → 明确同意后**原参数 + token** 重调。令牌 5 分钟过期、一次性、参数变化即失效。

## 风控协议（强制）

`risk_control_paused` → 立即停止重试，指引浏览器完成人机验证后 `cx_import_cookies`，再继续。

## 常用工作流

- **查作业**：`cx_list_courses` → `cx_s_list_homeworks(课程)` → `cx_s_get_homework_detail(作业URL)`（只读题干与附件，不作答）。
- **交作业**：detail → 宿主与用户共同整理 answers → `cx_s_submit_homework(submit=false)` 暂存 → 用户核对 → `cx_s_submit_homework(submit=true)`（★确认）。
- **下资料**：`cx_s_list_materials(课程)` → `cx_s_download_material(objectId, 目录)`。
- **考试**：`cx_s_list_exams(课程)` 只读列表与时间，**不进入答题**；提醒用户本人完成。

## 关于自动化工具（默认关闭）

`cx_s_simulate_video_task` 与 `cx_s_auto_answer_quiz` 属于逆向协议的自动化能力：

- 会话开始时若检测到这两个工具存在，告知用户已开启，并提示风险。
- 每次使用前必须口头提示：**可能违反平台条款与学校学术规范，存在成绩无效、账号处罚风险，后果自负**。
- 宿主不得主动建议使用自动化工具，仅在用户明确点名时才可调用。

## 错误处理速查

| errorType | 含义 | 处理 |
|---|---|---|
| login_required | 未登录 | 引导 `cx_login` / `cx_import_cookies` |
| confirmation_required | 等待确认 | 复述影响 → 同意 → 带 token 重调 |
| risk_control_paused | 命中验证码 | 停止重试 → 浏览器验证 → 导 Cookie |
| upstream_changed | 平台改版 | 展示 snippet，反馈开发者 |
