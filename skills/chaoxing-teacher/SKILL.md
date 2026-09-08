---
name: chaoxing-teacher
description: "学习通教师助手 - 用自然语言管理超星学习通课程、作业批改、成绩册、签到活动、班级通知与资料上传。关键词：学习通、超星、我教的课、班级、批改作业、成绩、发起签到、发通知、传资料"
version: "0.1.0"
author: "cxmcp"
---

# 学习通教师助手

> **目标**：通过 `cx-mcp-teacher` MCP server 的 `cx_t_*` 系列工具，用自然语言完成学习通教学管理操作。

## 前置条件（每次会话开始时检查）

1. 宿主已配置 `cx-mcp-teacher` MCP server（stdio）。未配置时给出下方配置说明，**不要**继续执行业务操作。
2. 先调用 `cx_session_status` 检查登录态：
   - `logged_in: true` → 直接执行业务。
   - `login_required` → 引导用户二选一：① 明文提供账号密码后调用 `cx_login`；② 浏览器登录后导出 Cookie 调用 `cx_import_cookies`。

### MCP 配置说明（宿主未配置时展示）

```json
{
  "mcpServers": {
    "chaoxing-teacher": {
      "command": "cx-mcp-teacher",
      "env": { "CX_COOKIE_FILE": "~/.chaoxing-mcp/teacher_cookies.json" }
    }
  }
}
```

## When to Use

用户明确提及学习通/超星的**教学管理**意图：查课程班级、看作业提交、批改打分、查成绩册、发起签到、看签到统计、发班级通知、上传课程资料。

## When NOT to Use（重要）

- 用户意图是**学生**操作（查我的作业、交作业、签到）→ 使用 `chaoxing-student` skill。
- 单纯闲聊或与学习通无关的任务。
- 用户要求**绕过平台验证、代签到、伪造位置** → 拒绝。

## 操作确认协议（强制，最高优先级）

对 ★ 高影响工具（`cx_t_review_homework` / `cx_t_create_signin` / `cx_t_send_notice` / `cx_t_upload_material`）：

1. 首次调用会返回 `errorType: confirmation_required` 与 `confirmToken`，**这是正常流程**，不是错误。
2. 必须向用户复述完整影响（课程、对象、分数/内容/时长），获得用户**明确同意**后才可继续。
3. 继续时携带**完全相同的参数** + `confirmToken` 重调。任何参数变化都会使令牌失效（需重新确认）。
4. 令牌 5 分钟过期、一次性。严禁跳过确认直接重试。

## 风控协议（强制）

任何工具返回 `errorType: risk_control_paused` 时：

1. **立即停止**该业务流的重试，不要连续调用。
2. 告知用户：学习通要求人机验证。
3. 指引用户浏览器打开学习通完成验证，然后 F12 导出 Cookie，调用 `cx_import_cookies`。
4. 导入成功后再继续原任务。

## 常用工作流

- **批改作业**：`cx_list_courses` → `cx_t_list_homeworks(课程)` → `cx_t_get_homework_submissions(作业URL)` → 逐个 `cx_t_download_submission` → 宿主 AI 评阅 → `cx_t_review_homework`（★确认）。
- **发起签到**：`cx_t_list_classes` → `cx_t_create_signin(课程, 类型, 时长)`（★确认）→ `cx_t_get_signin_status` 追踪。
- **发通知**：`cx_t_send_notice(课程, 标题, 正文)`（★确认）。

## 错误处理速查

| errorType | 含义 | 处理 |
|---|---|---|
| login_required | 未登录/会话失效 | 引导 `cx_login` 或 `cx_import_cookies` |
| confirmation_required | 等待用户确认 | 复述影响 → 取得同意 → 带 token 重调 |
| risk_control_paused | 命中验证码/滑块 | 停止重试，引导浏览器验证 + 导 Cookie |
| upstream_changed | 平台改版解析失败 | 向用户展示返回的 snippet，反馈开发者 |
| not_supported | 角色不匹配 | 确认应使用 student 版 |

## 风险声明

本工具链为学习通平台第三方协议实现，平台改版可能导致部分功能失效。所有写操作均需人工确认，请遵守学校教学规范。
