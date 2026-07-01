"""
@Author:shkstart
@Desc: 演示 ainvoke 的另一种常见写法：先启动模型任务，再继续执行当前流程
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


async def main():
    """更贴近原示例的写法。

    这里没有把模型调用和其他工作都拆成独立函数，而是在同一个业务流程里：
    1. 先用 create_task() 启动模型请求；
    2. 趁模型等待网络返回时，继续执行其他异步 I/O 工作；
    3. 真正需要模型结果时，再 await 这个模型任务。
    """
    print("=== 演示：先启动 ainvoke，再继续执行当前流程 ===")
    start_time = time.perf_counter()

    # 先把模型请求发出去。create_task() 会让协程进入事件循环开始运行。
    # 这一步不会立刻等模型完整返回，所以后面的代码可以继续执行。
    print(">>> 发起模型调用任务")
    model_task = asyncio.create_task(
        model.ainvoke("用一句话解释人工智能。")
    )

    # 这里模拟当前业务流程里的其他异步 I/O 工作。
    # 真实项目中可能是查数据库、读缓存、请求外部 API、加载用户信息等。
    print(">>> 模型请求已发出，继续处理其他异步 I/O 工作")
    for i in range(3):
        await asyncio.sleep(1)
        elapsed = time.perf_counter() - start_time
        print(f">>> 其他任务第 {i + 1} 步完成，已耗时 {elapsed:.2f}s")

    # 当业务流程走到需要模型结果的位置时，再 await 它。
    # 如果模型已经返回，这里会很快拿到结果；如果还没返回，就继续等待。
    print(">>> 现在需要模型结果，开始等待 model_task")
    response = await model_task

    end_time = time.perf_counter()
    print("\n=== 执行结果 ===")
    print(f"模型返回：{response.content}")
    print(f"总耗时：{end_time - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
