# 网络 I/O 与 CPU 密集：为什么有些任务适合 `asyncio`

学习 `asyncio` 时，一个非常关键的判断是：

```text
这个任务的大部分时间是在等待外部响应，还是在本地做 CPU 计算？
```

前者通常适合 `asyncio`；后者通常不适合只靠 `asyncio`。

## 1. I/O 密集型任务

I/O 密集型任务的特点是：程序发起一个请求后，大部分时间都在等待外部系统响应。

常见例子：

- 模型调用：等待模型服务商排队、推理、生成、返回响应。
- 数据库查询：等待数据库执行 SQL、读取数据、通过网络返回结果。
- HTTP 请求：等待外部 API 处理并返回。
- 向量库检索：等待向量数据库做 ANN 检索、过滤、排序并返回文档。

在这些场景里，本地 Python 大部分时间没有 CPU 计算要做，而是在等网络、磁盘或远程服务。

比如 LangChain 的异步模型调用：

```python
response = await model.ainvoke("你好")
```

可以理解成底层发生了类似这样的流程：

```text
await model.ainvoke(...)
  -> LangChain 底层调用异步 HTTP 客户端
  -> await http_client.post(...)
  -> 请求发到模型服务商
  -> 等待模型排队、推理、生成文本、云服务组装响应、网络传回
```

这段等待可能耗时几百毫秒到数秒。等待期间，当前协程可以暂停，把事件循环让出去，让其他协程继续推进。

这就是 `asyncio` 的优势：

```text
等待外部响应时，不要阻塞当前线程；
把事件循环让出去，去推进其他已经调度的任务。
```

## 2. CPU 密集型任务

CPU 密集型任务的特点是：程序大部分时间都在本地计算。

例如：

```python
async def heavy_cpu_work():
    total = 0
    for i in range(100_000_000):
        total += i
    return total
```

注意，即使这个函数写成了 `async def`，它也不一定是“异步友好”的。

原因是：函数体里没有 `await`，也没有等待外部 I/O。一旦它开始运行，就会一直占着事件循环所在的线程做 CPU 计算。

结果是：

```text
CPU 计算占住当前线程
事件循环没有机会调度其他协程
模型调用、数据库请求、HTTP 请求等任务都可能被卡住
```

所以，`async def` 不会自动让 CPU 计算并发。

## 3. 关键不是 async，而是有没有让路点

`asyncio` 是协作式调度。事件循环不会强行打断一个正在执行的协程。协程需要在 `await` 处主动让出控制权。

更准确的说法是：

```text
asyncio 并发的关键不是“有多个 async 函数”，
而是这些协程运行过程中会不会遇到 await，
并在等待 I/O 时把事件循环让出去。
```

这个“让路点”通常来自：

```python
await 网络 I/O
await 数据库 I/O
await asyncio.sleep(...)
await 异步文件/队列/锁等
await model.ainvoke(...)
```

如果一个协程中间没有任何 `await`，并且一直做 CPU 计算，那么它就没有协作式让出事件循环的机会。

## 4. “空闲时间片”的更准确说法

直觉上可以说：

```text
I/O 等待期间，当前协程有“空闲时间”，可以让其他协程运行。
```

但更准确的术语不是“时间片”。

在线程或操作系统调度里，时间片通常指操作系统分配给线程的 CPU 执行片段。`asyncio` 不是这种抢占式调度，而是协作式调度。

因此更准确地说：

```text
当前协程在 await 处主动让出事件循环。
```

或者：

```text
I/O 等待期间存在让路机会。
```

## 5. 如果 CPU 任务写在 async 函数里会怎样？

例如：

```python
async def heavy_cpu_work():
    total = 0
    for i in range(100_000_000):
        total += i
    return total


async def main():
    model_task = asyncio.create_task(model.ainvoke("你好"))
    result = await heavy_cpu_work()
    response = await model_task
```

这段代码的问题是：`heavy_cpu_work()` 虽然是协程函数，但内部没有 `await`。

当它开始运行后，会一直占着事件循环所在的线程。`model_task` 虽然已经被创建，但事件循环没有机会推进它。

也就是说：

```text
create_task() 只是把模型调用安排成后台任务；
但如果当前协程随后被 CPU 计算长期占住，
事件循环仍然无法调度这个后台任务。
```

## 6. CPU 密集任务该怎么处理？

### 小计算：直接执行

如果只是很小的计算，比如简单字符串处理、JSON 组装、少量列表过滤，直接写就可以。没必要把所有东西都复杂化。

### 中等计算：丢到线程池，避免堵住事件循环

如果计算会明显卡住事件循环，但还没有重到需要多进程，可以用：

```python
result = await asyncio.to_thread(cpu_heavy_function, arg1, arg2)
```

这会把同步函数放到另一个线程里执行。当前事件循环所在的线程可以继续调度其他协程。

注意：Python 有 GIL。对于纯 Python CPU 密集计算，线程池不一定能充分利用多核 CPU。但它至少可以避免把事件循环堵死。

### 重 CPU：使用进程池

真正重 CPU 的任务，更适合用进程池：

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor


def cpu_heavy_function(n):
    total = 0
    for i in range(n):
        total += i
    return total


async def main():
    loop = asyncio.get_running_loop()

    with ProcessPoolExecutor() as pool:
        result = await loop.run_in_executor(
            pool,
            cpu_heavy_function,
            100_000_000,
        )

    print(result)
```

多进程有独立的 Python 解释器和独立的 GIL，更适合真正 CPU 密集型任务。

## 7. 判断标准

可以用这张表快速判断：

| 任务类型 | 大部分时间花在哪里 | 推荐方式 |
|---|---|---|
| 模型调用 | 等模型服务商响应 | `await model.ainvoke(...)` |
| 数据库查询 | 等数据库执行和网络返回 | 异步数据库驱动 + `await` |
| HTTP 请求 | 等外部服务响应 | 异步 HTTP 客户端 + `await` |
| 向量库检索 | 等检索服务返回 | 异步向量库接口 + `await` |
| 少量本地计算 | 本地 CPU，很短 | 直接执行 |
| 中等 CPU 计算 | 本地 CPU，可能卡事件循环 | `asyncio.to_thread(...)` |
| 重 CPU 计算 | 本地 CPU，很耗时 | 进程池 / 多进程 / 外部计算服务 |

## 8. 最终总结

`asyncio` 适合 I/O 密集型任务，因为这些任务经常在等待外部系统响应。等待期间，当前协程可以在 `await` 处暂停，把事件循环让出去，让其他协程继续推进。

CPU 密集型任务不适合只靠 `asyncio`。如果一个协程一直在本地计算，并且没有 `await` 让路点，它会卡住事件循环，让其他异步任务无法推进。

一句话记忆：

```text
大部分时间在等外部响应：asyncio / await
大部分时间在本地计算：线程池、进程池或外部计算服务
```
