# GIL 与 no-GIL：CPython 多线程的核心限制

这篇笔记整理 Python 面试中常见的 GIL 问题，以及 Python 3.13、3.14、3.15 对 no-GIL / free-threaded Python 的最新进展。

截至 2026-06-30：

- Python 3.13 引入实验性的 free-threaded build。
- Python 3.14 的 free-threaded build 进入官方支持阶段，但仍然是可选构建，不是默认。
- Python 3.15 继续推进 free-threaded 生态，重点之一是 PEP 803：为 free-threaded builds 提供稳定 ABI，也就是 `abi3t`。

## 1. GIL 是什么

GIL 全称是 Global Interpreter Lock，中文通常叫“全局解释器锁”。

它是 CPython 解释器中的一个全局互斥锁。它的典型效果是：

```text
在一个 CPython 进程中，同一时刻通常只有一个线程能执行 Python 字节码。
```

注意这个描述里有几个限定：

- 它说的是 CPython，不是所有 Python 实现。
- 它限制的是同一进程内多个线程执行 Python 字节码。
- 它不等于 Python 不能做并发。
- 它不等于 Python 线程完全没用。

例如，I/O 等待、部分 C 扩展、NumPy / PyTorch 等底层 native 计算，在某些情况下仍然可以释放 GIL 或绕开 Python 字节码执行限制。

## 2. 为什么 CPython 要设计 GIL

GIL 的核心目的不是“故意限制性能”，而是保护 CPython 解释器内部状态，尤其是对象内存管理。

CPython 的对象生命周期主要依赖引用计数。

大致可以理解为：

```text
有一个变量引用对象，引用计数 +1
一个引用消失，引用计数 -1
引用计数变成 0，对象就可以被释放
```

如果多个线程同时修改同一个对象的引用计数，就可能发生竞态。

例如理论上应该加两次：

```text
初始 refcount = 10

线程 A 读取 refcount = 10
线程 B 读取 refcount = 10
线程 A 写回 11
线程 B 写回 11
```

正确结果应该是 12，但最后可能变成 11。引用计数错了，内存管理就可能出问题。

GIL 用一把大锁保护解释器内部很多关键操作，让 CPython 不必给每个对象、每个引用计数、每个内部结构都设计复杂的细粒度锁。

这个设计带来了几个好处：

- CPython 实现更简单。
- 单线程执行性能长期很好。
- C 扩展编写模型相对简单。
- 解释器内部状态更容易维护一致性。

但代价是：

```text
CPU 密集型 Python 多线程无法在多个 CPU 核心上真正并行执行 Python 字节码。
```

## 3. GIL 为什么影响线程并发

假设有两个线程：

```text
线程 A：执行 Python 计算
线程 B：执行 Python 计算
```

在带 GIL 的 CPython 中，它们要轮流拿到 GIL 才能执行 Python 字节码。

所以 CPU 密集型代码开多个 Python 线程时，通常不是：

```text
线程 A 在 CPU 核心 1 上跑
线程 B 在 CPU 核心 2 上跑
```

而更像：

```text
线程 A 拿到 GIL，跑一会儿
线程 A 释放 GIL
线程 B 拿到 GIL，跑一会儿
线程 B 释放 GIL
线程 A 再拿到 GIL
```

这种情况下，多线程可能不会更快，甚至因为锁竞争和线程切换更慢。

典型受影响的是纯 Python CPU 密集型任务：

```python
def cpu_heavy():
    total = 0
    for i in range(100_000_000):
        total += i
    return total
```

开多个线程跑这类函数，通常不能充分利用多核 CPU。

## 4. GIL 不影响什么

GIL 的影响要分场景看。

### I/O 密集型任务

例如：

- 网络请求
- 数据库查询
- 文件读写
- 模型 API 调用

这些任务大部分时间都在等待外部响应。等待 I/O 时，线程可以释放 GIL，所以多线程或异步 I/O 仍然有价值。

### C 扩展中的 native 计算

很多高性能库会把计算放到底层 C / C++ / Fortran / Rust 中，并在长时间计算时释放 GIL。

例如某些 NumPy、PyTorch、SciPy 操作。它们的并行能力不完全受 Python 字节码层面的 GIL 限制。

### 多进程

GIL 是进程内的锁。多个 Python 进程各自有自己的解释器和自己的 GIL。

所以 CPU 密集任务常用：

```python
multiprocessing
ProcessPoolExecutor
```

来绕开单进程 GIL 限制。

## 5. 其他语言为什么没有这个限制

准确地说，其他语言不是“没有并发问题”，而是选择了不同的内存管理和并发模型。

例如：

- Java / Go / .NET：运行时有自己的 GC、线程调度和内存模型。
- C++：开发者自己负责锁、原子操作、内存安全。
- Rust：通过所有权、借用检查、类型系统约束数据竞争。

这些语言通常没有 CPython 这种“整个解释器一把大锁”的设计，但它们仍然需要处理：

- 数据竞争
- 锁竞争
- 原子操作
- 内存可见性
- 线程安全容器
- 死锁

所以 GIL 是一种设计取舍：

```text
用一把大锁简化解释器内部并发安全，换来 CPU 密集型 Python 线程无法真正并行。
```

## 6. no-GIL / free-threaded Python 是什么

no-GIL 并不是“Python 以后不需要锁了”。

更准确地说，它是：

```text
让 CPython 可以在没有全局解释器锁的模式下运行，
使多个 Python 线程有机会在多个 CPU 核心上同时执行 Python 代码。
```

Python 官方现在更多使用的术语是 free-threaded Python 或 free-threaded build。

在 free-threaded 构建中，多个 Python 线程可以真正并行执行 Python 字节码。但这也意味着 CPython 内部和 C 扩展生态需要承担更多线程安全复杂度。

## 7. Python 3.13 / 3.14 / 3.15 的进展

### Python 3.13

Python 3.13 引入实验性的 free-threaded build。

这表示 no-GIL 方向正式进入 CPython 主线探索，但还处于实验阶段。

### Python 3.14

Python 3.14 的 free-threaded build 进入官方支持阶段。

但要注意：

```text
Python 3.14 不是默认无 GIL。
free-threaded build 仍然是可选构建。
```

这意味着它可以被更正式地测试、分发和适配，但普通用户默认安装的 CPython 通常仍然是带 GIL 的构建。

### Python 3.15

Python 3.15 继续推进 free-threaded 生态。

一个重要点是 PEP 803：Stable ABI for Free-Threaded Builds，也就是 `abi3t`。

为什么这重要？

Python 生态里大量包都有 C 扩展，例如：

- NumPy
- SciPy
- cryptography
- pydantic-core
- orjson
- PyO3 / Rust 扩展

这些扩展过去可能默认假设 GIL 存在。free-threaded Python 没有 GIL 后，C 扩展必须更明确地处理线程安全。

`abi3t` 的目标是给 free-threaded builds 提供稳定 ABI，降低库作者适配成本，推动 wheel 和构建生态支持 no-GIL Python。

所以 Python 3.15 的重点不是“默认 no-GIL 时代已经到来”，而是：

```text
继续为 no-GIL 的生态落地铺路。
```

## 8. 为什么现在要推进 no-GIL

主要原因是硬件和 Python 使用场景都变了。

### 多核 CPU 已经是常态

现代服务器和个人电脑都有多个 CPU 核心。GIL 让纯 Python 多线程很难充分利用多核。

### Python 越来越多用于高并发和计算密集场景

Python 已经广泛用于：

- 数据科学
- AI / ML
- Web 服务
- Agent 系统
- 数据处理
- 自动化和工程脚本

这些场景越来越需要更好的并行能力。

### 多进程方案成本高

过去 CPU 密集型任务常用多进程绕开 GIL，但多进程有代价：

- 进程启动成本更高。
- 内存不能像线程那样直接共享。
- 数据序列化和进程间通信麻烦。
- 部署和调试复杂度更高。

free-threaded Python 希望让多线程也能成为更自然的 CPU 并行方式。

### 过去不做，是因为代价太大

去掉 GIL 并不只是删掉一把锁。

必须重新处理：

- 引用计数线程安全
- 对象内存管理
- dict / list 等核心容器的并发安全
- C API 兼容
- C 扩展生态
- 单线程性能损耗

之前很多 no-GIL 尝试失败，一个重要原因是单线程性能下降太明显，或者生态破坏太大。

现在 PEP 703 方向的实现把性能损耗和兼容性问题控制到了更可接受的范围，所以才逐步进入官方支持阶段。

## 9. no-GIL 后是不是就不需要锁了

不是。

GIL 以前保护的是 CPython 解释器内部状态，不等于保护你的业务逻辑。

即使在有 GIL 的 Python 里，多个线程同时修改共享数据也可能有逻辑竞态。

例如：

```python
counter += 1
```

它看起来是一行，但底层可能包含读取、加一、写回多个步骤。

no-GIL 后，多线程真正并行执行 Python 代码，共享可变数据的竞态风险会更明显。

你仍然需要：

- `threading.Lock`
- 队列
- 原子操作
- 不可变数据结构
- 避免共享可变状态
- actor / message passing 等并发模型

no-GIL 提供的是“多线程可以真正并行执行 Python 代码”的能力，不是自动保证业务线程安全。

## 10. 面试回答模板

### 问：GIL 是什么？

可以答：

```text
GIL 是 CPython 的全局解释器锁。它保证同一进程内同一时刻通常只有一个线程执行 Python 字节码。它主要用于保护解释器内部状态和引用计数内存管理，简化 CPython 的线程安全实现。
```

### 问：GIL 有什么影响？

可以答：

```text
GIL 会限制纯 Python CPU 密集型多线程的并行能力。多个线程不能真正同时执行 Python 字节码，所以 CPU 密集任务用线程通常不能充分利用多核。I/O 密集任务受影响较小，因为等待 I/O 时可以释放 GIL；多进程也不受单进程 GIL 限制。
```

### 问：为什么 CPython 不一开始就去掉 GIL？

可以答：

```text
因为 GIL 让 CPython 的引用计数、对象管理和 C 扩展模型更简单，并且长期保证了较好的单线程性能。去掉 GIL 需要重构大量解释器内部机制，还要处理 C 扩展生态和单线程性能回退问题。
```

### 问：Python 3.14 / 3.15 是否已经没有 GIL？

可以答：

```text
不是默认没有 GIL。Python 3.13 引入实验性的 free-threaded build，Python 3.14 进入官方支持阶段，但仍是可选构建。Python 3.15 继续推进生态适配，例如 PEP 803 为 free-threaded builds 提供稳定 ABI，也就是 abi3t。默认 Python 是否切到 no-GIL 还需要后续阶段决定。
```

### 问：no-GIL 的意义是什么？

可以答：

```text
no-GIL 的目标是让 CPython 多线程能够真正利用多核 CPU 并行执行 Python 代码，降低 CPU 密集任务只能依赖多进程或 C 扩展释放 GIL 的限制。但 no-GIL 不等于业务代码自动线程安全，共享可变状态仍然需要锁或其他并发控制。
```

## 11. 最终总结

GIL 是 CPython 为了简化解释器内部线程安全和引用计数内存管理而设计的一把全局锁。它让 CPython 长期保持简单可靠和较好的单线程性能，但限制了纯 Python CPU 密集型多线程的多核并行能力。

no-GIL / free-threaded Python 的目标是让 Python 线程能够真正并行执行 Python 代码。Python 3.13 开始实验，3.14 进入官方支持但仍可选，3.15 继续推进 C 扩展 ABI 和生态适配。

一句话记忆：

```text
GIL 保护的是解释器内部安全；
代价是 CPU 密集型 Python 线程难以多核并行；
no-GIL 想释放多线程并行能力，
但会把更多线程安全责任交给解释器实现、扩展库和业务代码。
```
