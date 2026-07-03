import os

# ============================================================
# SMTP 邮箱配置
# ============================================================
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

_RECIPIENTS_RAW = os.environ.get("RECIPIENTS", "")
RECIPIENTS = [r.strip() for r in _RECIPIENTS_RAW.split(",") if r.strip()]

EMAIL_SUBJECT_PREFIX = "每日市场晨报"

# ============================================================
# 1. 市场指标
# ============================================================
MARKET_INDICATORS = [
    {"name": "VIX 恐慌指数",        "symbol": "^VIX",       "unit": ""},
    {"name": "VXN 纳指波动率",      "symbol": "^VXN",       "unit": ""},
    {"name": "美元指数 DXY",        "symbol": "DX-Y.NYB",   "unit": ""},
    {"name": "10年美债收益率",      "symbol": "^TNX",       "unit": "%"},
    {"name": "2年美债/联邦利率",    "symbol": "^IRX",       "unit": "%"},
    {"name": "波罗的海干散货 ETF",  "symbol": "BDRY",       "unit": "$"},
    {"name": "中国10年国债收益率",  "symbol": "CN10YT=RR",  "unit": "%"},
    {"name": "日本10年国债收益率",  "symbol": "^JNGB10Y",   "unit": "%"},
]

# ============================================================
# 2. 外汇汇率
# ============================================================
FOREX = [
    {"name": "在岸人民币 USDCNY",   "symbol": "CNY=X",      "unit": ""},
    {"name": "离岸人民币 USDCNH",   "symbol": "CNH=X",      "unit": ""},
    {"name": "日元/美元 USDJPY",    "symbol": "JPY=X",      "unit": ""},
    {"name": "欧元/美元 EURUSD",    "symbol": "EURUSD=X",   "unit": ""},
]

# ============================================================
# 3. 三大指数
# ============================================================
INDEXES = [
    {"name": "道琼斯工业", "symbol": "^DJI",  "unit": ""},
    {"name": "标普500",    "symbol": "^GSPC", "unit": ""},
    {"name": "纳斯达克",   "symbol": "^IXIC", "unit": ""},
    {"name": "纳斯达克100", "symbol": "^NDX", "unit": ""},
]

# ============================================================
# 4. 亚太指数
# ============================================================
APAC_INDEXES = [
    {"name": "日经225",   "symbol": "^N225", "unit": ""},
    {"name": "韩国KOSPI", "symbol": "^KS11", "unit": ""},
    {"name": "台湾加权",  "symbol": "^TWII", "unit": ""},
]
APAC_NOTE = "基于昨日收盘数据"

# ============================================================
# 5. 欧洲
# ============================================================
EUROPE = [
    {"name": "欧洲斯托克50", "symbol": "^STOXX50E", "unit": ""},
    {"name": "英国富时100",  "symbol": "^FTSE",     "unit": ""},
    {"name": "德国DAX",      "symbol": "^GDAXI",    "unit": ""},
]
EUROPE_NOTE = "基于昨日收盘数据"

# ============================================================
# 6. 中国指数
# ============================================================
CHINA_INDICES = [
    {"name": "上证指数",     "symbol": "000001.SS", "unit": ""},
    {"name": "恒生科技指数", "symbol": "^HSTECH",   "unit": ""},
    {"name": "科创50",      "symbol": "000688.SS", "unit": ""},
]
CHINA_INDICES_NOTE = "基于昨日收盘数据"

# ============================================================
# 7. 商品期货
# ============================================================
COMMODITIES = [
    {"name": "黄金",         "symbol": "GC=F",  "unit": "$"},
    {"name": "白银",         "symbol": "SI=F",  "unit": "$"},
    {"name": "原油",         "symbol": "CL=F",  "unit": "$"},
    {"name": "铜",           "symbol": "HG=F",  "unit": "$"},
    {"name": "铝",           "symbol": "ALI=F", "unit": "$"},
    {"name": "CRB 商品 ETF",  "symbol": "DBC",  "unit": "$"},
    {"name": "大豆",         "symbol": "ZS=F",  "unit": "$"},
    {"name": "棉花",         "symbol": "CT=F",  "unit": "$"},
    {"name": "玉米",         "symbol": "ZC=F",  "unit": "$"},
    {"name": "天然气",       "symbol": "NG=F",  "unit": "$"},
]

# ============================================================
# 8. 美股七姐妹
# ============================================================
MAGNIFICENT_SEVEN = [
    {"name": "苹果",   "symbol": "AAPL",  "unit": "$"},
    {"name": "微软",   "symbol": "MSFT",  "unit": "$"},
    {"name": "谷歌",   "symbol": "GOOGL", "unit": "$"},
    {"name": "亚马逊", "symbol": "AMZN",  "unit": "$"},
    {"name": "英伟达", "symbol": "NVDA",  "unit": "$"},
    {"name": "Meta",   "symbol": "META",  "unit": "$"},
    {"name": "特斯拉", "symbol": "TSLA",  "unit": "$"},
]

# ============================================================
# 9. 传统蓝筹
# ============================================================
BLUE_CHIPS = [
    {"name": "摩根大通",   "symbol": "JPM",    "unit": "$"},
    {"name": "伯克希尔B",  "symbol": "BRK-B",  "unit": "$"},
    {"name": "强生",       "symbol": "JNJ",    "unit": "$"},
    {"name": "可口可乐",   "symbol": "KO",     "unit": "$"},
    {"name": "波音",       "symbol": "BA",     "unit": "$"},
]

# ============================================================
# 10. 中国个股
# ============================================================
CHINA_STOCKS = [
    {"name": "贵州茅台",   "symbol": "600519.SS", "unit": "¥"},
    {"name": "腾讯控股",   "symbol": "0700.HK",   "unit": "HK$"},
    {"name": "新易盛",     "symbol": "300502.SZ", "unit": "¥"},
    {"name": "中际旭创",   "symbol": "300308.SZ", "unit": "¥"},
    {"name": "招商银行",   "symbol": "600036.SS", "unit": "¥"},
    {"name": "中国平安",   "symbol": "601318.SS", "unit": "¥"},
    {"name": "宁德时代",   "symbol": "300750.SZ", "unit": "¥"},
    {"name": "比亚迪",     "symbol": "002594.SZ", "unit": "¥"},
]
CHINA_STOCKS_NOTE = "基于昨日收盘数据"

# ============================================================
# 11. 半导体
# ============================================================
SEMICONDUCTORS = [
    {"name": "美光",             "symbol": "MU",    "unit": "$"},
    {"name": "希捷",             "symbol": "STX",   "unit": "$"},
    {"name": "费城半导体",        "symbol": "^SOX", "unit": ""},
    {"name": "DRAM 半导体 ETF",   "symbol": "SMH",  "unit": "$"},
    {"name": "英特尔",           "symbol": "INTC",  "unit": "$"},
    {"name": "ASML",             "symbol": "ASML",  "unit": "$"},
    {"name": "迈威尔",           "symbol": "MRVL",  "unit": "$"},
]

# ============================================================
# 12. 机器人与自动化
# ============================================================
ROBOTICS = [
    {"name": "全球机器人 ETF",  "symbol": "ROBO",       "unit": "$"},
    {"name": "深证机器人指数",  "symbol": "399350.SZ",  "unit": ""},
]
ROBOTICS_NOTE = "机器人指数为昨日收盘数据"

# ============================================================
# 13. 新能源与锂矿
# ============================================================
NEW_ENERGY = [
    {"name": "锂矿 LIT",         "symbol": "LIT",       "unit": "$"},
    {"name": "全球清洁能源 ICLN", "symbol": "ICLN",     "unit": "$"},
    {"name": "隆基绿能",         "symbol": "601012.SS", "unit": "¥"},
    {"name": "通威股份(多晶硅)", "symbol": "600438.SS", "unit": "¥"},
]
NEW_ENERGY_NOTE = "A 股标的数据为昨日收盘"

# ============================================================
# 14. 加密货币
# ============================================================
CRYPTO_IDS = ["bitcoin", "ethereum"]
CRYPTO_NAMES = {"bitcoin": "比特币 BTC", "ethereum": "以太坊 ETH"}
CRYPTO_UNITS = {"bitcoin": "$", "ethereum": "$"}
CRYPTO_VS_CURRENCY = "usd"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# ============================================================
# 财报日历个股列表（排除指数/ETF/商品/外汇/债券）
# ============================================================
EARNINGS_STOCKS = [
    # 七姐妹
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # 半导体
    "MU", "STX", "INTC", "ASML", "MRVL",
    # 传统蓝筹
    "JPM", "BRK-B", "JNJ", "KO", "BA",
    # 中国个股
    "600519.SS", "0700.HK", "300502.SZ", "300308.SZ",
    "600036.SS", "601318.SS", "300750.SZ", "002594.SZ",
    # 新能源
    "601012.SS", "600438.SS",
    # 纳指100核心成分（芯片/AI）
    "AVGO", "AMD", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "ARM",
    # 纳指100（软件/SaaS）
    "ADBE", "CRM", "NOW", "SNOW", "CRWD", "PANW", "DDOG", "TEAM",
    # 纳指100（互联网/消费）
    "NFLX", "COST", "PEP", "SBUX", "BKNG", "UBER", "ABNB",
    # 纳指100（生物医药）
    "AMGN", "GILD", "VRTX", "REGN", "ISRG", "MRNA",
    # 纳指100（金融/支付）
    "PYPL", "ADP", "INTU", "CME",
]

# ============================================================
# 放量预警阈值
# ============================================================
VOL_THRESHOLD = 3.0

# ============================================================
# ticker 备选
# ============================================================
TICKER_FALLBACKS = {
    "ALI=F":       ["JJU=F"],
    "CN10YT=RR":   ["CN10Y.BOND", "CN10YT", "511010.SS"],
    "^JNGB10Y":    ["JP10YT=RR", "JP10YT", "JP10Y", "2821.T", "1349.T"],
    "^HSTECH":     ["3032.HK"],
    "000001.SS":   ["510050.SS"],
    "^N225":       ["EWJ"],
    "DBC":         ["GSG", "PDBC"],
}

# ============================================================
# 贪婪指数
# ============================================================
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

# ============================================================
# 邮件模板颜色
# ============================================================
COLOR_UP         = "#d32f2f"
COLOR_DOWN       = "#2e7d32"
COLOR_UNCHANGED  = "#616161"
COLOR_BG_HEADER  = "#1a1a2e"
COLOR_BG_SECTION = "#f5f5f5"
COLOR_TEXT       = "#333333"
COLOR_TEXT_LIGHT = "#757575"
