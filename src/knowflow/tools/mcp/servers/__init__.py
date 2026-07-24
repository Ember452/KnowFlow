"""MCP 示例 Server 包 - 内置 stdio MCP Server 供演示/单测/评测.

注意: 不在 __init__ 中导入子模块, 避免 `python -m ...servers.demo` 子进程
启动时触发 "found in sys.modules after import of package" 警告.
"""
