"""演示 GPT-5.6 通过 OpenRouter 使用 Responses API 进行推理与多工具调用。"""

import os
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI


load_dotenv(override=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")
# 使用 OpenRouter 当前目录中实际存在的模型 slug 覆盖默认值。
MODEL_NAME = os.getenv("RESPONSES_MODEL", "openai/gpt-5.6-luna")

if not OPENROUTER_API_KEY or not OPENROUTER_BASE_URL:
    raise RuntimeError(
        "请先在项目根目录的 .env 中配置 OPENROUTER_API_KEY 和 OPENROUTER_BASE_URL"
    )


@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气。此示例返回固定数据，不发起真实 HTTP 请求。"""
    weather_by_city = {
        "北京": "晴，24 摄氏度，大风",
        "上海": "多云，27 摄氏度，湿度较高",
    }
    return weather_by_city.get(city, f"暂未准备 {city} 的演示天气数据")


@tool
def get_local_time() -> str:
    """获取运行此脚本的本机当前时间。"""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


# 关键点：这会将请求发往 <base_url>/responses，而非 <base_url>/chat/completions。
# 对 GPT-5.6 而言，推理参数与本地 function tools 应在这条路径上组合使用。
model = ChatOpenAI(
    model=MODEL_NAME,
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    use_responses_api=True,
    reasoning={"effort": "medium"},
)

# create_agent 负责 Agent 循环：模型提出 tool call 后，LangChain 在本地执行函数，
# 将结果作为 ToolMessage 交回模型，模型再基于结果给出最终回答。
agent = create_agent(
    model=model,
    tools=[get_weather, get_local_time],
    system_prompt="你是严谨的旅行助手。需要外部信息时必须使用提供的工具。",
)


def print_trace(messages: list) -> None:
    """以紧凑方式展示 Agent 的消息、工具调用和工具结果。"""
    for index, message in enumerate(messages, start=1):
        print(f"\n[{index}] {message.type}")

        if message.type == "ai" and message.tool_calls:
            for tool_call in message.tool_calls:
                print(f"  tool_call: {tool_call['name']}({tool_call['args']})")

        if message.type == "tool":
            print(f"  tool_result: {message.content}")
        elif message.content:
            print(f"  content: {message.content}")


def main() -> None:
    print("=== Responses API + GPT-5.6 + 多工具 + 推理 ===")
    print(f"模型: {MODEL_NAME}")

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请查询北京天气和当前本地时间，再给我一句简短的出行建议。",
                }
            ]
        }
    )

    print_trace(result["messages"])


if __name__ == "__main__":
    main()
