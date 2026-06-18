"""依赖解析器 - 解析 Skill 的关联工具并拓扑排序, 检测循环/缺失依赖.

resolve(skill, registry): 收集 skill.tools + skill.dependencies, 展开传递依赖
(每个工具的 requires), 拓扑排序输出需要激活的工具顺序. 循环依赖或引用未注册工具时抛错.
"""

from knowflow.core.exceptions import ValidationError
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition


class DependencyResolver:
    """Skill 依赖解析与拓扑排序."""

    def resolve(self, skill: SkillDefinition, registry: ToolRegistry) -> list[str]:
        """解析 skill 需要激活的工具(含传递依赖), 返回拓扑有序列表."""
        # 1. 收集初始工具集(skill.tools + dependencies), 校验已注册
        initial: list[str] = []
        for name in [*skill.tools, *skill.dependencies]:
            if not registry.has(name):
                raise ValidationError(
                    f"skill {skill.name} 引用未注册的工具: {name}",
                    details={"skill": skill.name, "missing_tool": name},
                )
            if name not in initial:
                initial.append(name)

        # 2. 展开传递依赖(requires), 同时校验
        graph: dict[str, list[str]] = {}
        visited: set[str] = set()
        stack: list[str] = list(initial)
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            requires = list(registry.get(cur).requires)
            for req in requires:
                if not registry.has(req):
                    raise ValidationError(
                        f"工具 {cur} 依赖未注册的工具: {req}",
                        details={"tool": cur, "missing": req},
                    )
                if req not in visited:
                    stack.append(req)
            graph[cur] = requires

        # 3. 拓扑排序(DFS), 检测循环
        order: list[str] = []
        state: dict[str, int] = {}  # 0=未访问 1=在途 2=完成

        def dfs(node: str, path: list[str]) -> None:
            if state.get(node, 0) == 1:
                idx = path.index(node) if node in path else 0
                cycle = [*path[idx:], node]
                raise ValidationError(
                    f"检测到循环依赖: {' -> '.join(cycle)}",
                    details={"cycle": cycle},
                )
            if state.get(node, 0) == 2:
                return
            state[node] = 1
            for dep in graph.get(node, []):
                dfs(dep, [*path, node])
            state[node] = 2
            order.append(node)

        for name in initial:
            dfs(name, [])

        return order
