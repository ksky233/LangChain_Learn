"""
@Author:shkstart
@Desc: 保留教材原始流程的 astream 示例，补充更准确的注释
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


async def demo_async_stream():
    """演示 astream 的异步流式调用。

    这个版本保留教材原始写法：先拿到 stream_resp，再做一段其他异步任务，
    最后才开始 async for 消费流式结果。

    注意：`model.astream(...)` 返回的是异步迭代器。仅仅创建这个对象时，
    通常还没有真正开始读取模型的流式响应。真正推进请求和接收 chunk，
    发生在下面的 `async for chunk in stream_resp` 里。
    """
    print("=== 演示：astream 的异步流式调用 ===")
    start_time = time.perf_counter()
    print("程序开始...")

    print(">>> 创建异步流对象 (astream)...")
    stream_resp = model.astream("请用一句话解释机器学习的基本概念。")

    print(">>> 先执行其他异步任务，稍后再消费模型流...")
    for i in range(3):
        # 这里用 asyncio.sleep() 模拟其他外部 I/O 等待。
        # 它会让出事件循环，但由于此版本还没进入 async for，
        # 模型流本身通常还不会被真正消费。
        await asyncio.sleep(1)
        print(f">>> 正在执行第 {i + 1} 个任务... (已耗时 {time.perf_counter() - start_time:.2f}s)")

    print(">>> 其他任务完成，现在开始读取模型流式结果...")
    print(">>> 流式输出: ", end="", flush=True)

    # async for 是消费 astream 的关键位置。
    # 每次模型服务端返回一个 chunk，这里就恢复执行一次；
    # 等待下一个 chunk 时，当前协程会把事件循环让出去。
    full_text = ""
    async for chunk in stream_resp:
        content = chunk.text if hasattr(chunk, "text") else chunk.content
        full_text += content
        print(content, end="", flush=True)

    end_time = time.perf_counter()
    print("\n>>> 流式输出结束")
    print(f">>> 完整内容: {full_text}")
    print(f"=== 总运行耗时: {end_time - start_time:.2f}s ===")


async def main():
    """主函数"""
    await demo_async_stream()


if __name__ == "__main__":
    asyncio.run(main())
