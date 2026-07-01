"""
@Author:shkstart
@Desc: 演示 astream 的异步流式调用方式
"""
import asyncio
import os
import time

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


# 从 .env 文件中加载 OpenRouter 配置，保持和前面 notebook 示例一致。
load_dotenv(override=True)
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
openrouter_base_url = os.getenv("OPENROUTER_BASE_URL")

if not openrouter_api_key or not openrouter_base_url:
    raise RuntimeError("请先在 .env 中配置 OPENROUTER_API_KEY 和 OPENROUTER_BASE_URL")

model = init_chat_model(
    api_key=openrouter_api_key,
    base_url=openrouter_base_url,
    model="gpt-5.4-mini",
)


def chunk_to_text(chunk) -> str:
    """兼容不同消息块对象，尽量取出可打印文本。"""
    if hasattr(chunk, "text"):
        return chunk.text
    if hasattr(chunk, "content"):
        return chunk.content if isinstance(chunk.content, str) else str(chunk.content)
    return str(chunk)


async def consume_model_stream() -> str:
    """消费模型的异步流式输出。

    astream() 和 ainvoke() 的区别是：
    - ainvoke() 等完整回答生成完，一次性返回 AIMessage。
    - astream() 在模型生成过程中不断产出 AIMessageChunk。

    注意：仅仅调用 `model.astream(...)` 通常还不会真正推进流式请求。
    真正的网络请求和 chunk 接收，是在进入 `async for` 消费这个异步迭代器时发生的。
    """
    print(">>> 任务 A：开始流式调用模型")
    full_text = ""

    # 这里的 async for 是关键：
    # 1. LangChain 底层会发起流式 HTTP 请求；
    # 2. 每当远端模型返回一小段 token/chunk，这里就恢复执行一次；
    # 3. 等待下一段 chunk 时，当前协程会再次让出事件循环。
    async for chunk in model.astream("请用三句话解释机器学习的基本概念。"):
        text = chunk_to_text(chunk)
        full_text += text
        print(text, end="", flush=True)

    print("\n>>> 任务 A：流式调用结束")
    return full_text


async def do_other_io_work():
    """模拟另一个异步 I/O 任务。"""
    print(">>> 任务 B：开始处理其他异步 I/O 工作")
    for i in range(3):
        # 用 asyncio.sleep() 模拟数据库/HTTP/文件上传等外部等待。
        # 这里会让出事件循环，所以模型流式任务可以继续接收 chunk。
        await asyncio.sleep(1)
        print(f"\n>>> 任务 B：第 {i + 1} 步完成")
    print(">>> 任务 B：其他异步 I/O 工作完成")
    return "其他异步任务完成"


async def main():
    """并发运行流式模型调用和另一个异步任务。"""
    print("=== 演示：astream 流式输出与其他异步任务并发执行 ===")
    start_time = time.perf_counter()

    # create_task() 的作用是把“消费模型流”的协程注册成后台任务。
    # 如果不 create_task，而是直接 await consume_model_stream()，
    # 当前 main 会一直等流式输出结束，才会继续执行后面的其他任务。
    stream_task = asyncio.create_task(consume_model_stream())
    other_task = asyncio.create_task(do_other_io_work())

    # gather() 同时等待两个任务完成。
    # 流式任务负责边生成边打印，other_task 负责模拟其他异步 I/O。
    full_text, other_result = await asyncio.gather(stream_task, other_task)

    end_time = time.perf_counter()
    print("\n=== 执行结果 ===")
    print(f"流式完整结果：{full_text}")
    print(f"其他任务：{other_result}")
    print(f"总耗时：{end_time - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
