"""
@Author:shkstart
@Desc: 演示 abatch 的异步批量调用方式
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


async def run_batch():
    """异步批量调用模型。

    abatch() 可以理解成 batch() 的异步版本。
    它接收一组互不依赖的输入，LangChain 会在客户端侧并发处理这些请求。

    返回值是一个列表，并且默认按输入顺序返回：
    第 1 个输入对应第 1 个输出，第 2 个输入对应第 2 个输出。
    """
    questions = [
        "用一句话说明深度学习与传统机器学习的区别。",
        "用一句话解释什么是向量数据库。",
        "用一句话解释什么是 RAG。",
    ]

    print(">>> 任务 A：开始 abatch 批量调用模型")

    # 这里的 await 是等待整批模型请求完成。
    # abatch 内部会并发推进多个模型调用；等待某个请求网络响应时，
    # 事件循环可以继续推进同批次的其他请求，或者推进外部的其他协程。
    #
    # max_concurrency 用来限制最大并发数，避免请求太多导致触发限流。
    responses = await model.abatch(
        questions,
        config={"max_concurrency": 2},
    )

    print(">>> 任务 A：abatch 批量调用完成")
    return questions, responses


async def do_other_io_work():
    """模拟另一个异步 I/O 任务。"""
    print(">>> 任务 B：开始处理其他异步 I/O 工作")
    for i in range(3):
        # 这里模拟当前程序还要等待数据库、HTTP API、文件上传等外部响应。
        # 等待期间会让出事件循环，abatch 的模型请求可以继续推进。
        await asyncio.sleep(1)
        print(f">>> 任务 B：第 {i + 1} 步完成")
    print(">>> 任务 B：其他异步 I/O 工作完成")
    return "其他异步任务完成"


async def main():
    """并发运行批量模型调用和另一个异步任务。"""
    print("=== 演示：abatch 批量调用与其他异步任务并发执行 ===")
    start_time = time.perf_counter()

    # create_task() 让 abatch 先作为后台任务启动。
    # 如果直接写 `questions, responses = await run_batch()`，
    # main 会等整批模型调用完成后，才会继续执行其他任务。
    batch_task = asyncio.create_task(run_batch())
    other_task = asyncio.create_task(do_other_io_work())

    (questions, responses), other_result = await asyncio.gather(batch_task, other_task)

    end_time = time.perf_counter()
    print("\n=== 执行结果 ===")
    for index, (question, response) in enumerate(zip(questions, responses), start=1):
        print(f"{index}. Q: {question}")
        print(f"   A: {response.content}")

    print(f"其他任务：{other_result}")
    print(f"总耗时：{end_time - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
