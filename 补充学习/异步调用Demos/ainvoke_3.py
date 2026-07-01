"""
@Author:shkstart
@Desc: 用 fake I/O 任务演示事件循环如何并发推进多个外部等待
"""
import asyncio
import time


async def fake_model_call():
    """模拟一次模型调用。

    真实项目中这里可能是 `await model.ainvoke(...)`。
    模型服务在远程机器上推理，当前程序大部分时间都在等待网络响应。
    """
    print(">>> 模型调用：开始请求远程模型")
    # 这里的 sleep(3) 不是业务逻辑里的“我要睡 3 秒”，而是在模拟：
    #
    #   await model.ainvoke(...)
    #     -> LangChain 底层调用异步 HTTP 客户端
    #     -> await http_client.post(...)
    #     -> 请求发到模型服务商
    #     -> 等待模型排队、推理、生成文本、云服务组装响应、网络传回
    #
    # 假设这一整段外部等待耗时 3 秒。在真实代码中，等待点可能是
    # LangChain / OpenAI SDK / httpx / aiohttp 等库内部的某个 await。
    #
    # 关键是：这 3 秒里当前 Python 协程没有 CPU 计算要做，只是在等远端响应。
    # 因此 await 会暂停 fake_model_call（当前协程），把事件循环让出去，让数据库查询、
    # HTTP 请求、向量库检索这些已经调度的协程继续推进。
    await asyncio.sleep(3)
    print(">>> 模型调用：完成")
    return "模型回答结果"


async def fake_database_query():
    """模拟一次数据库查询。"""
    print(">>> 数据库查询：开始查询用户历史")
    # 这里的 sleep(2) 模拟真实代码中的：
    #
    #   await async_db.fetch(...)
    #     -> 数据库驱动把 SQL 发给数据库服务器
    #     -> 数据库执行查询、读取磁盘/缓存、组装结果
    #     -> 结果通过网络返回给 Python 程序
    #
    # 假设这段外部等待耗时 2 秒。等待期间当前协程不需要占着线程空等，
    # 所以 await 会把事件循环让出去，让模型调用、HTTP 请求等任务继续跑。
    await asyncio.sleep(2)
    print(">>> 数据库查询：完成")
    return {"user_id": "u_001", "history_count": 8}


async def fake_http_request():
    """模拟一次 HTTP API 请求。"""
    print(">>> HTTP 请求：开始请求外部服务")
    # 这里的 sleep(1) 模拟真实代码中的：
    #
    #   await http_client.get(...)
    #     -> 发起 HTTP 请求
    #     -> 等待对方服务处理
    #     -> 等待响应从网络返回
    #
    # 这类等待时间取决于外部服务，而不是本地 Python 一直在计算。
    # await 让当前协程暂停，事件循环可以继续调度其他任务。
    await asyncio.sleep(1)
    print(">>> HTTP 请求：完成")
    return {"weather": "sunny"}


async def fake_vector_search():
    """模拟一次向量库检索。"""
    print(">>> 向量库检索：开始召回相关文档")
    # 这里的 sleep(2.5) 模拟真实代码中的：
    #
    #   await vector_store.asimilarity_search(...)
    #     -> embedding/query 请求发给向量库或检索服务
    #     -> 向量库做 ANN 检索、过滤、排序
    #     -> 返回相关文档
    #
    # 假设这段外部检索等待耗时 2.5 秒。当前协程在 await 处暂停后，
    # 事件循环仍能推进模型调用、数据库查询、HTTP 请求等其他协程。
    await asyncio.sleep(2.5)
    print(">>> 向量库检索：完成")
    return ["doc_001", "doc_014", "doc_102"]


async def main():
    """并发运行四个 fake I/O 任务。

    如果顺序执行，总耗时大约是：
        3 + 2 + 1 + 2.5 = 8.5 秒

    使用 asyncio.gather() 后，四个任务会一起进入事件循环。
    它们在等待外部响应时会让出事件循环，所以总耗时通常接近最慢的任务：
        max(3, 2, 1, 2.5) = 3 秒
    """
    print("=== 演示：模型、数据库、HTTP、向量库请求并发等待 ===")
    start_time = time.perf_counter()

    model_result, db_result, http_result, vector_result = await asyncio.gather(
        fake_model_call(),
        fake_database_query(),
        fake_http_request(),
        fake_vector_search(),
    )

    end_time = time.perf_counter()

    print("\n=== 执行结果 ===")
    print(f"模型结果：{model_result}")
    print(f"数据库结果：{db_result}")
    print(f"HTTP 结果：{http_result}")
    print(f"向量库结果：{vector_result}")
    print(f"总耗时：{end_time - start_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
