"""
@Author:shkstart
@Desc: 保留教材原始流程的 abatch 示例，补充更准确的注释
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


async def demo_async_batch():
    """演示 abatch 的异步批量调用。

    这个版本保留教材原始写法：
    1. 用 create_task() 先启动 abatch 后台任务；
    2. 当前协程继续执行其他异步任务；
    3. 最后 await batch_task 获取批量结果。
    """
    print("=== 演示：abatch 的异步批量调用 ===")
    start_time = time.perf_counter()
    print("程序开始...")

    questions = [
        "用一句话说明深度学习与传统机器学习的区别。",
        "中国首都在哪里？",
        "用一句话解释什么是 RAG。",
    ]

    print(">>> 发起异步批量调用 (abatch)...")

    # create_task() 会把 model.abatch(...) 注册成后台任务。
    # abatch 内部会并发处理多个输入，并默认按输入顺序返回结果。
    # config["max_concurrency"] 用来限制最大并发量，避免请求过多触发限流。
    batch_task = asyncio.create_task(
        model.abatch(
            questions,
            config={"max_concurrency": 2},
        )
    )

    print(">>> 批量任务已安排到后台，当前流程继续执行其他异步任务...")
    for i in range(3):
        # 这里用 asyncio.sleep() 模拟其他 I/O 等待。
        # 当前协程在 sleep 时会让出事件循环，后台 batch_task 就有机会推进模型请求。
        await asyncio.sleep(1)
        print(f">>> 正在执行第 {i + 1} 个任务... (已耗时 {time.perf_counter() - start_time:.2f}s)")

    print(">>> 其他任务已完成，现在获取后台批量任务结果...")

    # 如果 batch_task 已经完成，这里会立即拿到结果；
    # 如果还没完成，这里会继续等待整批模型调用结束。
    responses = await batch_task
    end_time = time.perf_counter()

    print("\n=== 执行结果 ===")
    for index, (question, response) in enumerate(zip(questions, responses), start=1):
        print(f"{index}. Q: {question}")
        print(f"   A: {response.content}")

    print(f"=== 总运行耗时: {end_time - start_time:.2f}s ===")


async def main():
    """主函数"""
    await demo_async_batch()


if __name__ == "__main__":
    asyncio.run(main())
