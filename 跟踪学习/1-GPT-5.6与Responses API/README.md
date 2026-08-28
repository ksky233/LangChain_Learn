# GPT-5.6 与 Responses API

> 本专题记录 2026-08 的 API 能力与兼容性。模型、网关和 API 均可能继续演进；实际接入前仍应查看对应模型和网关的最新文档。

## 1. 先区分：模型、API 端点与 LangChain

`GPT-5.6` 是模型系列；`Chat Completions API` 和 `Responses API` 是两条调用端点；LangChain 则是上层统一接口。切换到 Responses API 后，`invoke()`、`stream()`、`bind_tools()` 和 `create_agent()` 仍可照常使用。

```text
LangChain ChatOpenAI / create_agent
             |
             +-- use_responses_api=False  -> /v1/chat/completions
             |
             +-- use_responses_api=True   -> /v1/responses
```

GPT-5.6 同时支持 Chat Completions 与 Responses，并不是模型被强制“换到了”后一条端点。两条端点的能力组合并不完全相同。

## 2. GPT-5.6 多工具推理的关键限制

需要记住的不是“工具和思考不能共存”，而是这一个特定组合：

```text
Chat Completions + function tools + reasoning_effort
```

在 GPT-5.6 上，该组合会被 OpenAI 拒绝。因此给 GPT-5.6 做带本地函数工具的 Agent 时，不应使用默认的 Chat Completions 路径再开启 `reasoning_effort`。

正确组合是：

```text
Responses API + function tools + reasoning={"effort": "medium"}
```

Responses API 本来就面向 Agent 循环：模型可以推理、提出一个或多个工具调用、读取工具结果，再继续推理并生成回答。LangChain 的 `create_agent()` 仍负责本地工具的执行和循环编排。

`reasoning.mode`、`reasoning.context` 与 GPT-5.6 的 `effort="max"` 属于 Responses API 的高级能力；Chat Completions 仅能使用部分 `reasoning.effort` 能力。

## 3. 通过 OpenRouter 使用时的边界

OpenRouter 提供 OpenAI 兼容的 `/api/v1/responses` 端点，因此可以将 `ChatOpenAI` 的 `base_url` 指向 OpenRouter 并显式设置 `use_responses_api=True`。

但是它与直连 OpenAI 有一个很重要的差别：OpenRouter 的 Responses API 当前是 **Beta 且无状态**。

- 不能依赖 `store=True` 或 `previous_response_id`；两者会被 OpenRouter 拒绝。
- 多轮对话应由应用侧保留完整消息历史；在 LangChain/LangGraph 中，通常使用 `checkpointer + thread_id`。
- OpenAI 的托管 `file_search`、`code_interpreter`、`hosted shell`、MCP 等服务端工具不能因为协议兼容就默认认为能经 OpenRouter 完整使用。应按 OpenRouter 文档、模型和实际路由提供商逐项验证。
- 本地 Python 工具最稳定：模型产生 tool call，LangChain 在本地执行函数并把 `ToolMessage` 回传给模型。

因此，这个示例只使用两个本地工具，专注验证“Responses API + 推理 + 多工具”的核心组合。

## 4. Responses API 会替代哪些 LangChain 功能？

它会重叠一部分能力，但不是 LangChain/LangGraph 的替代品。

| Responses API / OpenAI 托管能力 | LangChain 生态中的对应能力 | 学习与工程建议 |
| --- | --- | --- |
| `previous_response_id`、服务端会话状态 | LangGraph checkpointer、消息历史 | 直连 OpenAI 可选前者；OpenRouter 不支持，应使用后者。 |
| 内置 Web Search | `langchain-tavily`、DuckDuckGo 等搜索工具 | 内置工具接入快；LangChain 搜索工具更可替换、更便于控制数据源。 |
| OpenAI File Search | Retriever、向量库、RAG 链路 | 托管方案少运维；LangChain RAG 支持多种向量库和检索策略。 |
| Code Interpreter、Hosted Shell | 自定义 `@tool`、Sandbox 工具 | 托管工具省基础设施；自定义工具便于安全、权限与业务规则控制。 |
| 原生 function calling | `@tool`、`bind_tools()`、`create_agent()` | 两者不是替代关系：Responses 负责协议，LangChain 负责统一工具定义和 Agent 循环。 |
| 原生流式事件 | `stream()`、`astream()`、`astream_events()` | LangChain 将不同供应商的事件收敛为统一 Runnable 接口。 |

LangGraph 的 checkpoint、长短期记忆、Middleware、人工审批、状态机、工具执行策略和可观测性仍属于应用编排层，Responses API 不会替代它们。

## 5. 何时选哪条路径

- **普通对话、无工具或不需要推理**：Chat Completions 足够，兼容性也通常更成熟。
- **GPT-5.6 + 本地工具 + 思考模式**：使用 Responses API，并显式设置 `use_responses_api=True`。
- **需要 OpenAI 托管工具或服务端会话**：使用直连 OpenAI 的 Responses API，并核对模型支持矩阵。
- **经 OpenRouter 或要保持多模型可移植性**：仍可使用 Responses API，但把会话历史和记忆交给 LangGraph；服务端工具逐项验证。

## 6. 示例说明与运行

`responses_api_agent.py` 定义了 `get_weather` 与 `get_local_time` 两个本地工具，要求 GPT-5.6 同时调用它们并给出总结。它故意使用：

```python
use_responses_api=True
reasoning={"effort": "medium"}
```

这样工具和推理处在 `/responses` 路径，而不是会出问题的 `/chat/completions` 路径。

项目根目录的 `.env` 需要已有：

```env
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

可选地设置 `RESPONSES_MODEL` 覆盖默认模型名；模型名必须以 OpenRouter 当前模型目录为准。

```powershell
uv run python ".\跟踪学习\1-GPT-5.6与Responses API\responses_api_agent.py"
```

本示例会产生一次真实模型调用并消耗 OpenRouter 额度。

## 7. 参考资料

- [OpenAI GPT-5.6 Sol 模型能力](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
- [LangChain ChatOpenAI: Responses API](https://docs.langchain.com/oss/python/integrations/chat/openai#responses-api)
- [LangChain Open SWE：GPT-5.6 与 function tools 的 Chat Completions 限制](https://github.com/langchain-ai/open-swe/blob/main/docs/CUSTOMIZATION.md)
- [OpenRouter Responses API（无状态、Beta）](https://openrouter.ai/docs/api_reference/responses/overview)
