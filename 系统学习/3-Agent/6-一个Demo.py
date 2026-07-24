# 9.1 模型的初始化
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

# 从.env文件中加载环境变量
load_dotenv(override=True)

# 模型的初始化
model = init_chat_model(
    model="gpt-5.4-mini",
    model_provider="openai",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("OPENROUTER_BASE_URL")
)

# ====================== 工具的定义 ======================
# 9.2 工具的定义
from langchain_core.tools import tool
import math
from datetime import datetime, timedelta

@tool
def get_weather(city: str) -> str:
    """获取指定城市的实时天气
    支持中国主要城市的天气查询

    Args:
        city: 城市名称, 如"北京"、"上海"、"深圳"等

    Returns:
        包含温度、天气状况、空气质量的详细信息

    Examples:
        get_weather("北京") 返回 "多云, 15-22℃, 空气质量良"
    """
    weather_db = {
        "北京": "多云, 15-22℃, 空气质量良, 湿度 45%",
        "上海": "小雨, 18-22℃, 空气质量优, 湿度 60%",
        "深圳": "晴天, 22-28℃, 空气质量优, 湿度 70%",
        "成都": "阴天, 16-23℃, 空气质量良, 湿度 55%",
        "杭州": "晴天, 17-24℃, 空气质量优, 湿度 72%",
        "广州": "多云, 21-29℃, 空气质量良, 湿度 52%"
    }
    result = weather_db.get(city)
    if result:
        return f"{city}: {result}"
    else:
        return f"抱歉, 暂不支持查询{city}的天气信息。当前支持: 北京、上海、深圳、成都、杭州、广州"

@tool
def calculator(expression: str) -> str:
    """执行数学计算
    支持基本运算符 (+、-、*、/、**) 和常用数学函数

    Args:
        expression: 数学表达式, 可以包含:
            - 基本运算: 2 + 3 * 10, 10 / 5, 100 / 4
            - 幂运算: 2 ** 10
            - 函数: sqrt(16), abs(-5), pow(2, 3)

    Returns:
        计算结果或错误信息

    Examples:
        calculator("2 + 3 * 4") 返回 "14"
        calculator("sqrt(16)") 返回 "4.0"
    """
    try:
        # 安全的数学运算环境
        safe_functions = {
            "sqrt": math.sqrt,
            "pow": pow,
            "round": round,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "pi": math.pi,
            "e": math.e
        }
        result = eval(expression, {"__builtins__": {}}, safe_functions)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算出错: {str(e)}\n提示: 请检查表达式格式, 支持的函数有 sqrt, abs, pow, sin, cos, tan, log"

@tool
def get_time_info(query_type: str = "current") -> str:
    """获取时间相关信息

    Args:
        query_type: 查询类型
            - "current": 当前时间
            - "date": 今天日期
            - "tomorrow": 明天日期
            - "yesterday": 昨天日期
            - "weekday": 星期几

    Returns:
        时间信息字符串

    Examples:
        get_time_info("current") 返回 "2025年1月25日 14:30:25"
        get_time_info("weekday") 返回 "星期六"
    """
    now = datetime.now()
    if query_type == "current":
        return now.strftime("当前时间: %Y年%m月%d日 %H:%M:%S")
    elif query_type == "date":
        return now.strftime("今天是: %Y年%m月%d日")
    elif query_type == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.strftime("明天是: %Y年%m月%d日")
    elif query_type == "yesterday":
        yesterday = now - timedelta(days=1)
        return yesterday.strftime("昨天是: %Y年%m月%d日")
    elif query_type == "weekday":
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return f"今天是{weekdays[now.weekday()]}"
    else:
        return f"不支持的查询类型: {query_type}。支持: current, date, tomorrow, yesterday, weekday"

@tool
def convert_currency(amount: float, from_curr: str, to_curr: str) -> str:
    """支持主要货币之间的实时汇率转换

    Args:
        amount: 金额数值
        from_curr: 源货币代码 (CNY/USD/EUR/GBP/JPY/HKD)
        to_curr: 目标货币代码 (CNY/USD/EUR/GBP/JPY/HKD)

    Returns:
        转换结果

    Examples:
        convert_currency(100, "CNY", "USD") 返回 "100 CNY = 14.00 USD"
    """
    # 汇率表 (相对于 CNY)
    exchange_rates = {
        "CNY": 1.0,    # 人民币
        "USD": 0.14,   # 美元
        "EUR": 0.13,   # 欧元
        "GBP": 0.11,   # 英镑
        "JPY": 20.8,   # 日元
        "HKD": 1.08,   # 港币
    }
    # 货币名称
    currency_names = {
        "CNY": "人民币", "USD": "美元", "EUR": "欧元",
        "GBP": "英镑", "JPY": "日元", "HKD": "港币"
    }
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr not in exchange_rates:
        return f"不支持的源货币: {from_curr}。支持的货币: CNY, USD, EUR, GBP, JPY, HKD"
    if to_curr not in exchange_rates:
        return f"不支持的目标货币: {to_curr}。支持的货币: CNY, USD, EUR, GBP, JPY, HKD"

    # 转换逻辑: 先转为 CNY, 再转为目标货币
    cny_amount = amount / exchange_rates[from_curr]
    result_amount = cny_amount * exchange_rates[to_curr]

    from_name = currency_names[from_curr]
    to_name = currency_names[to_curr]
    return f"{amount} {from_name} ({from_curr}) = {result_amount:.2f} {to_name} ({to_curr})"

@tool
def search_info(keyword: str, category: str = "all") -> str:
    """搜索各类信息

    Args:
        keyword: 搜索关键词
        category: 搜索分类
            - "product": 搜索产品
            - "news": 搜索新闻
            - "all": 搜索所有

    Returns:
        搜索结果
    """
    # 模拟数据库
    products = {
        "手机": "iPhone 15 (¥5999), 小米14 (¥3999), 华为Mate60 (¥6999)",
        "笔记本": "MacBook Pro ¥12999, ThinkPad X1 ¥9999, 华为MateBook (¥7999)",
        "耳机": "AirPods Pro (¥1999), Sony WH-1000XM5 (¥2499)"
    }
    news = {
        "AI": "1. GPT-5即将发布 2. AGI芯片市场增长 300% 3. 新AI法规出台",
        "科技": "1. 量子计算新突破 2. 6G 技术测试 3. 新能源车销量创新高"
    }
    results = []
    if category in ["product", "all"]:
        for key, value in products.items():
            if keyword in key or keyword in value:
                results.append(f"【产品】{key}: {value}")
    if category in ["news", "all"]:
        for key, value in news.items():
            if keyword in key or keyword in value:
                results.append(f"【新闻】{key} 相关: {value}")
    if results:
        return "\n".join(results)
    else:
        return f"未找到关于 '{keyword}' 的{category}信息"

# ====================== agent的创建 ======================
# 9.3 agent的创建
from langchain.agents import create_agent

class SmartAssistant:
    """多功能智能助手"""
    def __init__(self):
        # 初始化模型
        self.model = model
        # 工具列表
        self.tools = [
            get_weather,
            calculator,
            get_time_info,
            convert_currency,
            search_info
        ]
        # 系统提示词
        system_prompt = """你是一个多功能智能助手, 可以帮助用户:
        🌤 查询天气: 使用 get_weather 工具
        🧮 数学计算: 使用 calculator 工具
        ⏰ 时间查询: 使用 get_time_info 工具
        💱 货币转换: 使用 convert_currency 工具
        🔍 信息搜索: 使用 search_info 工具

        重要提示:
        1. 仔细阅读用户问题, 确定需要使用哪个工具
        2. 如果需要多个工具, 按顺序调用
        3. 总是用友好、专业的语气回答
        4. 如果工具返回了数据, 要通俗易懂的解释给用户
        5. 如果无法完成任务, 诚实地告诉用户原因

        请始终使用中文回答。
        """
        # 创建 agent
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=system_prompt
        )
        # 对话历史
        self.messages = []

    def chat(self, user_input: str) -> str:
        """添加用户输入"""
        self.messages.append({"role": "user", "content": user_input})
        # 调用 agent
        result = self.agent.invoke({"messages": self.messages})
        # 更新消息历史
        self.messages = result["messages"]
        # 返回最后一条AI消息
        for msg in reversed(self.messages):
            if msg.type == "ai" and msg.content:
                return msg.content
        return "抱歉, 我无法处理这个请求。"

    def reset(self):
        """重置对话历史"""
        self.messages = []

# ====================== 主程序 ======================
# 9.4 主程序
def main():
    # 初始化助手
    assistant = SmartAssistant()
    print("=" * 40)
    print("🤖 多功能智能助手 (LangChain 1.2)")
    print("=" * 40)
    print("我可以帮你: ")
    print("🌤 查询天气")
    print("🧮 数学计算")
    print("⏰ 时间查询")
    print("💱 货币转换")
    print("🔍 信息搜索")
    print("\n输入 'quit' 退出, 输入 'reset' 重置对话\n")

    demos = [
        "北京今天天气怎么样?",
        "现在几点了?",
        "100美元等于多少人民币?",
        "sqrt(25) + 3 * 8"
    ]
    print("=== 示例问题 ===")
    for demo in demos:
        print(f"你: {demo}")
        response = assistant.chat(demo)
        print(f"助手: {response}\n")
        # 重置对话
        assistant.reset()

    print("=== 进入交互模式 ===")
    print("-" * 40)
    while True:
        user_input = input("你: ")
        if user_input.lower() == "quit":
            print("👋 再见!")
            break
        if user_input.lower() == "reset":
            assistant.reset()
            print("✅ 对话已重置")
            continue
        if not user_input.strip():
            continue
        # 调用助手
        response = assistant.chat(user_input)
        print(f"助手: {response}\n")

if __name__ == "__main__":
    main()