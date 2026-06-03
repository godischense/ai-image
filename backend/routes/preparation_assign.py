"""
负责人自动分配模块

功能描述：
    根据海报文案中包含的国家名称，自动分配对应的负责人。
    基于产品2025分工表格（Excel）的数据分析，建立国家到负责人的映射关系。

实现逻辑：
    1. 维护国家→负责人列表的映射表（一个国家可有多人共同负责）
    2. 扫描文案中的国家名称，匹配后返回对应的负责人姓名（多人用"/"分隔）
    3. 匹配到多个国家时，以第一个匹配到的为准
    4. 没有匹配到任何国家时，返回空字符串
"""

# 国家到负责人的映射表
# 基于产品2025分工表格分析：
#   绿色项目 → Yuli 负责
#   蓝色项目 → Yancy 负责
#   一个国家可以有多人共同负责（值设为列表）
COUNTRY_PERSON_MAP = {
    # Yuli（绿色）负责的国家
    "希腊": ["Yuli"],
    "马耳他": ["Yuli"],
    "葡萄牙": ["Yuli"],
    "德国": ["Yuli"],
    "斯洛伐克": ["Yuli"],
    "芬兰": ["Yuli"],
    "瑞典": ["Yuli"],
    "菲律宾": ["Yuli"],
    "韩国": ["Yuli"],
    "马来西亚": ["Yuli"],
    "泰国": ["Yuli"],
    "中国香港": ["Yuli"],
    "澳大利亚": ["Yuli"],
    "新西兰": ["Yuli"],
    "斐济": ["Yuli"],
    # Yancy（蓝色）负责的国家
    "土耳其": ["Yancy"],
    "瓦努阿图": ["Yancy"],
    "圣基茨": ["Yancy"],
    "格林纳达": ["Yancy"],
    "圣卢西亚": ["Yancy"],
    "安提瓜": ["Yancy"],
    "多米尼克": ["Yancy"],
    "格鲁吉亚": ["Yancy"],
    "新加坡": ["Yancy"],
    "日本": ["Yancy"],
    "美国": ["Yancy"],
    "加拿大": ["Yancy"],
    "几内亚比绍": ["Yancy"],
    # Yuli + Yancy 共同负责的国家
    "西班牙": ["Yuli", "Yancy"],
    "爱尔兰": ["Yuli", "Yancy"],
    "瑙鲁": ["Yuli", "Yancy"],
    "圣多美": ["Yuli", "Yancy"],
}

# 国家名称列表（按名称长度降序排列，优先匹配更长、更具体的国家名）
# 例如 "圣基茨" 和 "圣卢西亚" 需要区分
_COUNTRY_NAMES = sorted(COUNTRY_PERSON_MAP.keys(), key=len, reverse=True)


def assign_person_in_charge(text: str) -> str:
    """
    根据文案内容自动分配负责人

    功能描述：
        扫描传入的文案文本，查找是否包含已知的国家名称。
        如果匹配到国家，返回对应的负责人姓名（多人用"/"分隔）；否则返回空字符串。

    实现逻辑：
        1. 如果传入的文本为空，直接返回空字符串
        2. 按名称长度降序遍历国家列表（避免短名称误匹配）
        3. 返回第一个匹配到的国家对应的负责人列表（可能有多人），用"/"连接
        4. 没有匹配则返回空字符串

    参数：
        text: 文案文本（可以是海报文案或生图提示词）

    返回：
        str: 负责人姓名（如 "Yuli"、"Yuli/Yancy"），未匹配时返回空字符串
    """
    if not text or not text.strip():
        return ""
    for country in _COUNTRY_NAMES:
        if country in text:
            persons = COUNTRY_PERSON_MAP[country]
            return "/".join(persons)
    return ""
