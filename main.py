"""Operit 部署入口：cx-mcp-student（学习通学生版 MCP server）。

供宿主按 cwd=插件目录 启动：python3 main.py
"""
from cxmcp.cli import main_student

if __name__ == "__main__":
    main_student()
