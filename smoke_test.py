#!/usr/bin/env python3
"""cxmcp 实机冒烟测试（在你能登录学习通的机器上运行）。

用法:
    python smoke_test.py                  # 仅启动 server 并列出工具
    python smoke_test.py login            # 登录 + 拉课程列表 + 会话检查
    python smoke_test.py login --role teacher

依赖: pip install "cxmcp @ file://<本目录路径>" 或在本目录 pip install -e .
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


async def main() -> int:
    parser = argparse.ArgumentParser(description="cxmcp 实机冒烟测试")
    parser.add_argument("action", nargs="?", default="list", choices=["list", "login"])
    parser.add_argument("--role", default="student", choices=["student", "teacher"])
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--automation", action="store_true")
    args = parser.parse_args()

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cxmcp.cli", args.role] + (["--enable-automation"] if args.automation else []),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"[OK] server 已启动，共 {len(tools.tools)} 个工具:")
            for t in tools.tools:
                print("  -", t.name)

            if args.action != "login":
                return 0
            if not args.username or not args.password:
                print("[!!] login 需要 --username 与 --password")
                return 2

            r = await session.call_tool(
                "cx_login", {"username": args.username, "password": args.password}
            )
            payload = json.loads(r.content[0].text)
            print("[login]", json.dumps(payload, ensure_ascii=False))
            if not payload.get("ok"):
                return 1

            r2 = await session.call_tool("cx_list_courses", {})
            courses = json.loads(r2.content[0].text)
            print(f"[courses] 共 {courses.get('count')} 门:")
            for c in courses.get("courses", []):
                print(f"  - {c['name']}  courseId={c['courseId']} clazzId={c['clazzId']} cpi={c['cpi']}")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
