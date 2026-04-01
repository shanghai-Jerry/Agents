# Tools

共享工具包。所有 tool 通过 `@register_tool` 装饰器注册到全局 `ResourceRegistry`，供子 Agent 和权限系统引用。

## Tool 总览

| Tool 名称 | 文件 | 分组 | 依赖 | 描述 |
|---|---|---|---|---|
| `think_tool` | `thinking.py` | `core` | 无 | 战略反思工具，用于任务过程中的自我评估和决策 |
| `tavily_search` | `search.py` | `search` | tavily-python | Tavily 网络搜索，获取实时信息 |
| `fetch_webpage_content` | `fetch_webpage_content.py` | `search` | httpx, markdownify | 抓取网页内容并转为 Markdown |
| `sandbox_exec` | `sandbox.py` | `code` | modal | 在 Modal 沙箱中执行命令 |
| `sandbox_upload` | `sandbox.py` | `code` | modal | 上传文件到 Modal 沙箱 |
| `sandbox_download` | `sandbox.py` | `code` | modal | 从 Modal 沙箱下载文件 |

## 分组（Groups）

| 分组名 | Tool 列表 | 用途 |
|---|---|---|
| `core` | think_tool | 基础能力，所有 Agent 通用 |
| `search` | tavily_search, fetch_webpage_content | 信息获取和搜索 |
| `code` | sandbox_exec, sandbox_upload, sandbox_download | 代码执行和沙箱操作 |

## 架构说明

每个子 Agent 的 `get_default_tools()` 返回 **全部** 已注册 tool 实例。实际能力边界由 `permissions.yaml` **唯一决定** — 权限系统在注册时通过白名单过滤 tools。添加新子 Agent 时只需创建 `permissions.yaml`，无需编写自定义 `tools.py`。

## 权限配置

在子 Agent 或主 Agent 的 `permissions.yaml` 中，可以通过 **tool 名称** 或 **分组名** 授权：

```yaml
permissions:
  tools:
    - think_tool              # 精确授权单个 tool
  groups:
    - core                    # 授权整个分组（自动包含组内所有 tool）
    - search                  # 授权 search 分组下的 tavily_search + fetch_webpage_content
```

## 添加新 Tool

1. 在 `tools/` 下创建新模块（如 `tools/my_tool.py`）
2. 使用 `@register_tool` 装饰器注册：

```python
from agents.resources import register_tool

@register_tool(group="search", description="My tool description")
def my_tool(query: str) -> str:
    """Tool docstring."""
    return f"Result: {query}"
```

3. 在 `tools/__init__.py` 的 `_import_optional_tools()` 中添加导入
4. 在对应 Agent 的 `permissions.yaml` 中授权
