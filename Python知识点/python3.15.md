# Python 3.15 重点新特性整理

这篇笔记基于视频 ASR 文字稿、截图代码片段，以及 Python 官方 3.15 文档整理。

截至 2026-06-30，Python 3.15 还不是最终正式版。根据 PEP 790，当前已经发布到 `3.15.0 beta 3`，最终版计划在 2026-10-01 发布。`3.15.0 beta 1` 之后原则上不再加入新功能，所以主要特性基本已经冻结，但文档细节仍可能继续调整。

## 1. 总览

Python 3.15 中比较值得关注的特性包括：

- PEP 814：新增内置类型 `frozendict`
- PEP 661：新增内置类型 `sentinel`
- PEP 810：显式延迟导入 `lazy import`
- PEP 798：推导式中支持 `*` / `**` 解包
- PEP 686：默认文本编码改为 UTF-8
- PEP 799：新增 `profiling` 包和 Tachyon 采样式性能分析器
- PEP 803：free-threaded builds 的稳定 ABI，即 `abi3t`

视频里重点讲的是前五个，其中 `frozendict`、`sentinel`、`lazy import` 最值得细看。

## 2. `frozendict`：不可变字典

Python 3.15 新增了内置类型 `frozendict`。

它可以理解成“不可变版本的 dict”：

```python
config = frozendict({
    "path": "~",
    "ttl": 100,
})

config["ttl"] = 200
# TypeError: 'frozendict' object does not support item assignment
```

不过要注意，`frozendict` 不是 `dict` 的子类，而是一个新的内置 mapping 类型。它实现了 `collections.abc.Mapping` 协议，保留插入顺序。

### 2.1 构造方式

```python
empty = frozendict()

from_kwargs = frozendict(path="~", ttl=100)

from_dict = frozendict({
    "path": "~",
    "ttl": 100,
})

from_pairs = frozendict([
    ("path", "~"),
    ("ttl", 100),
])
```

`frozendict` 的 key 必须可哈希，和普通 `dict` 一样。value 可以不可哈希，但如果 value 不可哈希，那么这个 `frozendict` 本身也不可哈希。

```python
hash(frozendict(path="~", ttl=100))  # 可以

hash(frozendict(items=[]))           # TypeError，因为 list 不可哈希
```

### 2.2 用途一：安全返回默认配置

截图中的第一组代码是在讲“返回不可变数据”。

以前如果用普通 `dict` 保存默认值，可能会出现调用者误改全局默认配置的问题：

```python
DEFAULT: dict[str, str | int] = {
    "path": "~",
    "ttl": 100,
}


class Cache:
    def get_default(self) -> dict[str, str | int]:
        return DEFAULT
```

这个版本有隐患：

```python
cache = Cache()
default = cache.get_default()
default["ttl"] = 0

print(DEFAULT)
# {"path": "~", "ttl": 0}
```

调用者修改了返回值，也就直接改掉了全局 `DEFAULT`。

以前常见解决方式是返回一份拷贝：

```python
DEFAULT: dict[str, str | int] = {
    "path": "~",
    "ttl": 100,
}


class Cache:
    def get_default(self) -> dict[str, str | int]:
        return dict(DEFAULT)
```

这样比较安全，但每次调用都会复制一份，有额外 CPU 和内存开销。

Python 3.15 可以直接使用 `frozendict`：

```python
DEFAULT: frozendict[str, str | int] = frozendict({
    "path": "~",
    "ttl": 100,
})


class Cache:
    def get_default(self) -> frozendict[str, str | int]:
        return DEFAULT
```

因为 `DEFAULT` 本身不可变，所以可以直接返回，不必每次复制。

### 2.3 用途二：作为缓存 key

普通 `dict` 是可变对象，因此不可哈希，不能作为另一个字典的 key：

```python
params = {"path": "~", "ttl": 100}

cache = {}
cache[params] = "result"
# TypeError: unhashable type: 'dict'
```

如果函数接收 `**kwargs`，想把参数组合作为缓存 key，也会遇到这个问题：

```python
class Cache:
    def __init__(self):
        self.cache_: dict[object, str] = {}

    def get_cache(self, **kwargs) -> str | None:
        return self.cache_.get(kwargs)  # 错误：kwargs 是 dict，不可哈希
```

以前常见做法是把 `kwargs.items()` 转成 tuple，或者自己封装 key 对象：

```python
key = tuple(sorted(kwargs.items()))
```

Python 3.15 可以用 `frozendict` 更直接表达：

```python
class Cache:
    def __init__(self):
        self.cache_: dict[frozendict[str, object], str] = {}

    def get_cache(self, **kwargs) -> str | None:
        return self.cache_.get(frozendict(kwargs))
```

这个写法的好处是语义更清楚：

```text
我不是想把 dict 强行变成 tuple；
我是想把这组参数冻结成一个不可变 mapping，然后作为缓存 key。
```

### 2.4 重要限制：浅层不可变

`frozendict` 是浅层不可变，不是深度不可变。

```python
d = frozendict({
    "items": [],
})

d["items"] = [1, 2, 3]
# TypeError，外层 mapping 不能改

d["items"].append("changed")
print(d)
# frozendict({'items': ['changed']})
```

外层 key 到 value 的绑定不可变，但如果 value 本身是可变对象，比如 list，仍然可以修改这个 list。

所以：

```text
frozendict 保证 mapping 结构不可改；
不保证整个对象图深度不可变。
```

## 3. `sentinel`：标准化哨兵对象

Python 3.15 新增了内置 `sentinel`，用于创建唯一的哨兵值。

哨兵值常用于区分：

```text
用户主动传了 None
用户根本没有传参数
```

### 3.1 问题：`None` 既可能是默认值，也可能是有效输入

截图中的第一个例子大概是：

```python
def print_bool(val=None):
    if val is None:
        print("please input a value")
        return

    print(bool(val))


print_bool(123)   # True
print_bool()      # please input a value
print_bool(None)  # please input a value
```

这个函数想表达：

```text
如果用户没传值，提示请输入；
如果用户传了值，就打印 bool(value)。
```

但问题是：`None` 既被用作默认值，又可能是用户主动传进来的值。

如果用户想知道：

```python
bool(None)
```

结果应该是：

```python
False
```

但上面的函数会误判成“用户没传值”。

### 3.2 旧方案：`object()` 创建私有哨兵

以前常见写法是：

```python
_MISSING = object()


def print_bool(val=_MISSING):
    if val is _MISSING:
        print("please input a value")
        return

    print(bool(val))


print_bool(123)   # True
print_bool()      # please input a value
print_bool(None)  # False
```

这个版本逻辑上是对的。

原因是 `_MISSING` 是一个唯一对象。用户不传参数时，`val` 才会是它；用户传 `None` 时，`val` 就是正常的 `None`。

但这个写法有几个问题：

- `repr(_MISSING)` 很丑，通常是 `<object object at 0x...>`
- 语义不够标准，看起来像临时技巧
- 类型标注不清楚
- copy / pickle 等场景可能有额外问题

尤其是类型标注会变得别扭。

假如函数只想接受 `int` 或 `None`，但又要支持 `_MISSING`：

```python
_MISSING = object()


def print_bool(val: int | None | object = _MISSING):
    if val is _MISSING:
        print("please input a value")
        return

    print(bool(val))
```

这里的 `object` 太宽了。因为所有对象都是 `object`，类型标注等于放开了几乎任意输入。

这不是我们的真实意图。

### 3.3 新方案：`sentinel`

Python 3.15 可以写：

```python
_MISSING = sentinel("_MISSING")


def print_bool(val: int | None | _MISSING = _MISSING):
    if val is _MISSING:
        print("please input a value")
        return

    print(bool(val))


print_bool(123)   # True
print_bool()      # please input a value
print_bool(None)  # False
```

这里 `_MISSING` 是一个真正的哨兵对象。

它的好处是：

- `repr` 简洁，默认就是传入的名字
- 是唯一对象，仍然用 `is` 判断
- 可以在类型表达式中直接使用
- copy / deepcopy 会保留 identity
- 如果能通过模块名和变量名导入，也可以 pickle 并保持 identity

判断哨兵时推荐使用：

```python
if val is _MISSING:
    ...
```

不要用：

```python
if not val:
    ...
```

因为哨兵对象本身是 truthy 的，而且业务上我们关心的是“是不是这个唯一对象”，不是它的布尔值。

## 4. `lazy import`：显式延迟导入

Python 3.15 新增了 `lazy import` 语法。

普通 import 是 eager import，也就是执行到 import 语句时立刻加载模块：

```python
import tqdm
```

Python 会立刻：

```text
查找 tqdm
读取文件
编译/加载字节码
执行模块顶层代码
tqdm 自己再导入更多依赖
```

如果这个模块很重，但当前运行路径根本用不到它，就会浪费启动时间和内存。

### 4.1 视频中的场景

比如一个模块里有两个函数：

```python
import tqdm


def function():
    return "普通功能"


def download(items):
    for item in tqdm.tqdm(items):
        ...
```

用户可能只是想用：

```python
function()
```

但只要导入这个模块，`tqdm` 就已经被加载了。

Python 3.15 可以改成：

```python
lazy import tqdm


def function():
    return "普通功能"


def download(items):
    for item in tqdm.tqdm(items):
        ...
```

执行到 `lazy import tqdm` 时，Python 不会立刻加载 `tqdm`，而是先在当前模块绑定一个 lazy proxy。直到第一次真正使用 `tqdm` 时，才触发真实导入。

也可以写：

```python
lazy from tqdm import tqdm


def download(items):
    for item in tqdm(items):
        ...
```

### 4.2 观察是否真正导入

官方 PEP 中类似这样的例子：

```python
import sys

lazy import json

print("json" in sys.modules)  # False，模块还没真正加载

text = json.dumps({"hello": "world"})

print("json" in sys.modules)  # True，第一次使用时才加载
```

### 4.3 全局启用 lazy imports

视频中提到可以通过命令行参数把普通 import 也变成 lazy：

```powershell
python -X lazy_imports=all app.py
```

也可以通过 `sys` API 控制：

```python
import sys


def only_myapp(importing, imported, fromlist):
    return imported.startswith("myapp.")


sys.set_lazy_imports_filter(only_myapp)
sys.set_lazy_imports("all")
```

这表示：全局进入 lazy imports 模式，但只有过滤器允许的模块才真正 lazy。

### 4.4 注意点

`lazy import` 不是无脑替换所有 import。

官方文档提到一些限制：

- `lazy import` 只能在模块顶层使用
- 不能放在函数内部
- 不能放在 class body 内
- 不能放在 `try` / `except` / `finally` 块内
- `lazy from module import *` 不允许
- `lazy from __future__ import ...` 不允许

另外，lazy import 会改变模块顶层副作用发生的时间。

例如某个模块 import 时会注册插件、打补丁、读取配置、启动日志等，改成 lazy 后这些副作用会推迟到第一次使用时发生。这类模块要谨慎。

所以更稳妥的结论是：

```text
lazy import 适合重模块、低频使用路径、CLI 启动优化；
但不应该盲目把所有 import 都 lazy。
```

## 5. 推导式中支持解包

Python 3.15 允许在 list / set / dict comprehension，以及 generator expression 中使用 `*` / `**` 解包。

以前可以写：

```python
it1 = [1, 2]
it2 = [3, 4]

items = [*it1, *it2]
```

但如果有一组 iterables：

```python
parts = [[1, 2], [3, 4], [5]]
```

以前常见写法是双层循环：

```python
flat = [x for part in parts for x in part]
```

Python 3.15 可以写成：

```python
flat = [*part for part in parts]
# [1, 2, 3, 4, 5]
```

set 也可以：

```python
groups = [{1, 2}, {2, 3}, {4}]

merged = {*group for group in groups}
# {1, 2, 3, 4}
```

dict 可以使用 `**`：

```python
dicts = [
    {"a": 1},
    {"b": 2},
    {"a": 3},
]

merged = {**d for d in dicts}
# {"a": 3, "b": 2}
```

如果 key 重复，后面的值覆盖前面的值，和普通 `{**d1, **d2}` 行为一致。

generator expression 也支持：

```python
flat_iter = (*part for part in parts)
```

它的含义类似：

```python
def generator():
    for part in parts:
        for item in part:
            yield item
```

这个特性主要是让“展平多个 iterable”或“合并多个 dict”的代码更直观。

## 6. 默认文本编码改为 UTF-8

Python 3.15 根据 PEP 686，将 UTF-8 作为默认文本编码。

以前如果写：

```python
with open("data.txt") as f:
    text = f.read()
```

Python 会使用系统 locale 默认编码。不同系统、不同区域设置可能不一样，比如 Windows 中文环境里可能遇到 GBK / cp936，Linux/macOS 上常见 UTF-8。

这会导致跨平台代码容易出现乱码：

```text
同一个文件，在一台机器能读，在另一台机器乱码或报 UnicodeDecodeError。
```

Python 3.15 默认使用 UTF-8 后，这类问题会少很多。

不过实际写业务代码时，仍然推荐显式写编码：

```python
with open("data.txt", encoding="utf-8") as f:
    text = f.read()
```

原因是：

```text
显式 encoding 更清楚；
读写历史文件、GBK 文件、第三方数据文件时仍可能需要指定非 UTF-8。
```

## 7. Tachyon：新的采样式性能分析器

Python 3.15 新增了 `profiling` 包，用来统一组织 Python 内置 profiling 工具。

其中比较值得关注的是 Tachyon，也就是新的高频统计采样 profiler，位于：

```python
profiling.sampling
```

它和传统 `cProfile` 这类 deterministic profiler 不同。

传统 profiler 通常会记录每次函数调用和返回，信息很细，但开销更高。

采样式 profiler 的思路是：

```text
每隔很短时间采一次当前调用栈；
采样足够多之后，就能统计程序主要时间花在哪里。
```

官方文档提到 Tachyon 的特点包括：

- 可以附加到正在运行的 Python 进程
- 不要求改代码或重启进程
- 开销极低，适合生产环境排查
- 支持 wall time、CPU time、GIL-holding time、exception handling time 等模式
- 支持火焰图等多种输出格式
- 支持 async-aware profiling

这类工具适合回答：

```text
程序卡在哪里？
CPU 时间主要耗在哪里？
哪个线程持有 GIL 时间最多？
async 任务到底在等什么？
```

## 8. free-threaded 相关：`abi3t`

Python 3.15 还继续推进 no-GIL / free-threaded 生态。

重点是 PEP 803：Stable ABI for Free-Threaded Builds，也就是 `abi3t`。

这个特性面向 C 扩展生态。它的意义是：

```text
让 C 扩展可以面向 free-threaded CPython 构建稳定 ABI，
降低第三方库适配 no-GIL Python 的成本。
```

这不表示 Python 3.15 默认没有 GIL。

更准确的状态是：

```text
Python 3.13：引入实验性 free-threaded build
Python 3.14：free-threaded build 进入官方支持阶段，但仍可选
Python 3.15：继续补齐 C 扩展 ABI 和生态能力
```

## 9. 一页速记

| 特性 | 解决什么问题 | 简单记忆 |
|---|---|---|
| `frozendict` | 不可变 mapping、可作为 key、安全返回默认配置 | 冻住外层 dict |
| `sentinel` | 区分“没传值”和“传了 None” | 标准哨兵对象 |
| `lazy import` | 减少启动时无用 import 成本 | 用到时才真正导入 |
| 推导式解包 | 展平多个 iterable / 合并多个 dict | `[*x for x in xs]` / `{**d for d in ds}` |
| UTF-8 默认编码 | 减少跨平台默认编码差异 | 默认不再依赖系统 locale |
| Tachyon | 低开销性能采样 | 生产排查更友好 |
| `abi3t` | free-threaded C 扩展 ABI | no-GIL 生态铺路 |

## 10. 参考资料

- Python 3.15 What's New：https://docs.python.org/3.15/whatsnew/3.15.html
- PEP 790，Python 3.15 Release Schedule：https://peps.python.org/pep-0790/
- PEP 814，`frozendict`：https://peps.python.org/pep-0814/
- PEP 661，`sentinel`：https://peps.python.org/pep-0661/
- PEP 810，Explicit lazy imports：https://peps.python.org/pep-0810/
- PEP 798，Unpacking in comprehensions：https://peps.python.org/pep-0798/
