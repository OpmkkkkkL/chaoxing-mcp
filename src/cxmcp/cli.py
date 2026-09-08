"""CLI 双入口：cx-mcp-teacher / cx-mcp-student。

日志一律走 stderr；stdout 属于 MCP stdio 协议，绝不能污染。
"""

from __future__ import annotations

import argparse
import logging
import sys


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,  # 关键：stdout 是协议通道
    )


def _main(role: str) -> None:
    parser = argparse.ArgumentParser(prog=f"cx-mcp-{role}", description=f"学习通{role} MCP server")
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http", "sse"], default="stdio",
        help="传输方式（默认 stdio，宿主即插即用）",
    )
    parser.add_argument("--host", default="127.0.0.1", help="streamable-http 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="streamable-http 端口")
    parser.add_argument("--cookie-file", default=None, help="Cookie JSON 路径（默认 ~/.chaoxing-mcp/<role>_cookies.json）")
    parser.add_argument(
        "--enable-automation",
        action="store_true",
        help="【学生版】开启自动化工具（视频任务点模拟/AI 答题）。风险自负。",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    from .server import build_server

    if role == "student" and args.enable_automation:
        logging.getLogger("cxmcp").warning(
            "自动化工具已开启：视频任务点模拟与 AI 答题可能违反平台条款与学术规范，后果自负"
        )

    mcp = build_server(
        role,
        enable_automation=args.enable_automation,
        cookie_file=args.cookie_file,
    )
    mcp.run(transport=args.transport, host=args.host, port=args.port)


def main_teacher() -> None:
    _main("teacher")


def main_student() -> None:
    _main("student")


if __name__ == "__main__":
    # 支持 `python -m cxmcp.cli teacher|student`：把角色位置参数从 argv 中剥掉
    if len(sys.argv) > 1 and sys.argv[1] in ("teacher", "student"):
        role = sys.argv.pop(1)
    else:
        role = "student"
    _main(role)
