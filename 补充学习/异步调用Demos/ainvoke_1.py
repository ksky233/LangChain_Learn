"""
@Author:shkstart
@Desc: 演示 ainvoke 的异步调用方式
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


async def call_model():
    """异步调用模型。

    ainvoke() 会发起一次模型请求，并在模型完整返回后给出最终结果。
    等待模型响应属于 I/O 等待，适合放在 async 函数中 await。
    """
    print(">>> 任务 A：开始调用模型")
    response = await model.ainvoke("用一句话解释人工智能。")
    print(">>> 任务 A：模型调用完成")
    return response.content


async def do_other_io_work():
    """模拟另一个异步 I/O 任务。

    这里用 asyncio.sleep() 只是为了模拟等待数据库、HTTP API、
    文件上传、消息队列等外部 I/O 的过程。真实业务里通常不是单纯 sleep。
    """
    print(">>> 任务 B：开始处理其他异步 I/O 工作")
    for i in range(3):
        await asyncio.sleep(1)
        print(f">>> 任务 B：第 {i + 1} 步完成")
    print(">>> 任务 B：其他异步 I/O 工作完成")
    return "其他异步任务完成"


async def main():
    """并发运行两个异步任务。

    如果两个任务顺序执行，总耗时大致是：
        模型调用耗时 + 其他 I/O 任务耗时

    使用 create_task() 后，两个任务会在同一个事件循环中并发等待。
    总耗时通常更接近两个任务里较慢的那个，而不是二者相加。
    """
    print("=== 演示：ainvoke 与其他异步任务并发执行 ===")
    start_time = time.perf_counter()

    # create_task() 会把协程注册成后台任务，让它先开始运行。
    model_task = asyncio.create_task(call_model())
    other_task = asyncio.create_task(do_other_io_work())

    # gather() 会同时等待多个异步任务，并按传入顺序返回结果。
    model_result, other_result = await asyncio.gather(model_task, other_task)

    end_time = time.perf_counter()
    print("\n=== 执行结果 ===")
    print(f"模型返回：{model_result}")
    print(f"其他任务：{other_result}")
    print(f"总耗时：{end_time - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
