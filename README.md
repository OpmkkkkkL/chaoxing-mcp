# cxmcp — 学习通 MCP Server（教师版 / 学生版）+ 配套 Skills

参考 [Cr-GH0/chaoxing-agent](https://github.com/Cr-GH0/chaoxing-agent) 与
[Aemiser/chaoxing_mcp](https://github.com/Aemiser/chaoxing_mcp) 的逆向成果自研的
超星学习通 MCP server。**纯 HTTP 协议模拟，无浏览器、无 WebDriver、无油猴依赖。**

## ⚠️ 使用声明

- 本项目为学习通平台**第三方协议实现**，平台改版可能导致功能失效；
- 视频/测验自动化能力默认关闭，开启后可能**违反平台条款与所在院校学术规范**，
  存在成绩无效、账号处罚风险，后果自负；
- 密码仅在登录调用内存中使用；Cookie 以 0600 权限存本地 JSON。

## 组成

| 目录 | 说明 |
|---|---|
| `chaoxing-mcp/` | MCP server 包，双入口 `cx-mcp-teacher` / `cx-mcp-student` |
| `chaoxing-teacher-skill/` | WorkBuddy/CodeBuddy 教师版 Skill 插件 |
| `chaoxing-student-skill/` | WorkBuddy/CodeBuddy 学生版 Skill 插件 |

工具规模：共用 5 + 教师 12 + 学生 11；学生版加 `--enable-automation` 追加 2 个自动化工具。

## 安装

```bash
cd chaoxing-mcp
pip install -e .            # 或 uv pip install -e .
cx-mcp-student --help       # 验证入口
```

## 接入宿主（stdio，即插即用）

```json
{
  "mcpServers": {
    "chaoxing-teacher": {
      "command": "cx-mcp-teacher",
      "env": { "CX_COOKIE_FILE": "~/.chaoxing-mcp/teacher_cookies.json" }
    },
    "chaoxing-student": {
      "command": "cx-mcp-student",
      "env": { "CX_COOKIE_FILE": "~/.chaoxing-mcp/student_cookies.json" }
    }
  }
}
```

- 远程模式：`cx-mcp-student --transport streamable-http --host 127.0.0.1 --port 8000`
  （**不要**绑定公网）
- 自动化（学生版）：`cx-mcp-student --enable-automation` 或环境变量 `CX_ENABLE_AUTOMATION=1`

## 登录方式

1. **账号密码**：`cx_login`（登录页 `t=true` 时走 AES-CBC 加密提交 `/fanyalogin`）。
   平台要求短信/二次验证时返回 `login_verification_required`，不绕过。
2. **Cookie 导入**：浏览器登录学习通 → F12 → 复制 Cookie（`uid/_uid/fid/vc3` 等）→
   `cx_import_cookies` 传入 `[{name, value, domain, path}]`。

## 安全设计（借鉴 chaoxing-agent）

- **两阶段确认**：批改/发通知/发起签到/上传/正式提交/自动化操作，首次调用返回
  `confirmation_required` + 一次性令牌（SHA-256 参数指纹绑定，5 分钟 TTL），
  参数变化即失效，防重放、防 TOCTOU；
- **风控即暂停**：HTTP 202 / antispider 跳转 → 返回 `risk_control_paused` 与指引，
  不自动过验证码；
- **回读验证**：提交类操作以刷新列表核对状态为准，HTTP 200 不等于成功；
- 日志全部走 stderr，stdout 仅承载 MCP stdio 协议。

## 实机校准（重要）

本仓库协议实现基于参考项目的公开逆向知识 + mock 单测（36 个，全绿）。
2026-09-09 已在真实账号（学生，17 门课）上跑通：`cx_login`/Cookie 导入、
`cx_list_courses`、作业/考试/章节列表均返回真实数据。

上线前可先跑：

```bash
python smoke_test.py login --role student --username 手机号 --password 密码
```

登录与课程列表属高确定性端点；签到/成绩/通知/上传/自动化端点随平台模板变动，
失败时会返回**候选端点探测记录**，按记录抓包更新 `src/cxmcp/api/` 中对应 URL 即可。

### 『没有内容』不等于『模板改版』

列表类接口一律遵循：先按模板选择器取行，取到 0 行时用
`api/pagestate.is_empty_page()` 判别页面是否明示空状态
（`暂无内容 / 暂无数据 / 尚未发布 …`），是则返回空列表，只有两者都不成立才抛
`UpstreamChanged`。此前作业/考试/资料页在没布置任务时会误报"模板可能改版"，
把调用方引去追一个不存在的 bug。

章节树同理：新版课程主页（`stucoursemiddle` 302 后的
`/mooc-ans/mycourse/studentcourse`）把章节**服务端渲染**在
`<div class="timeline">` 里，`levelone/leveltwo/levelthree` 三层，
`chapterId` 从链接里取。容器存在但为空（只剩 `<!-- 第一级开始 -->` 注释）
= 老师尚未发布章节，返回 `[]`。

## 批量调用的节流

学习通对高频请求会跳 `antispiderShowVerify.ac` 风控。串行遍历多门课时
**每次调用之间留 3~5 秒**；一旦返回 `risk_control_paused` 就停手，
不要重试硬闯（需人工在浏览器过一次验证或重导 Cookie）。

## 开发

```bash
pip install -e ".[dev]"
pytest tests/ -q
```

## 目录

```
src/cxmcp/
├── config.py      # 环境变量/CLI 配置
├── crypto.py      # 登录 AES-CBC（固定 TRANSFER_KEY）
├── session.py     # 会话/Cookie 原子持久化/TLS 兼容/风控守卫
├── confirm.py     # 两阶段确认令牌
├── api/           # courses / chapters / work / files / exams / signin / teacher / automation
├── tools/         # MCP 工具注册（common / teacher / student / automation）
├── server.py      # build_server(role, enable_automation)
└── cli.py         # stdio / streamable-http 双传输入口
```

## 许可

MIT。与超星官方无关联。
