"""
爬虫配置常量
原 trend_scraper.py 顶部的所有配置和常量，集中管理。
"""

# ==================== 教育领域搜索关键词池 ====================
SEARCH_KEYWORDS = [
    # === DSE 最新动态 ===
    "DSE 2025 2026 最新政策 香港考评局",
    "DSE 放榜 2025 成绩 分数线",
    "DSE 报考人数 2025 2026 统计",
    "DSE 改革 最新 方案",
    "JUPAS 2025 2026 改选 志愿填报",
    "港八大 录取 2025 最新数据",
    # === 港澳台联考 ===
    "港澳台联考 2025 2026 报名 最新",
    "全国联招 录取分数线 2025 最新",
    "港澳台联考 报考人数 2025",
    # === 内地高校招生 ===
    "内地高校 招收港籍生 2025 2026 最新政策",
    "暨南大学 华侨大学 港澳台招生 2025",
    "内地985 211 港籍生 录取 最新",
    "港澳子弟学校 内地 最新政策",
    # === 香港中小学插班 ===
    "香港中小学插班 2025 2026 最新政策",
    "香港中小学 自行分配学位 统一派位 2025",
    "香港直资学校 插班 报名 最新",
    "跨境学童 香港上学 最新政策 2025",
    # === 身份与政策 ===
    "香港永居 非永居 升学差异 最新政策",
    "回乡证 港籍生 内地升学 最新",
    "双非港宝 升学 最新政策 2025",
    # === 备考与课程 ===
    "DSE 公民科 备考 2025 最新",
    "DSE M1 M2 选科 最新 要求",
    "DSE 英文科 保底 最新路径",
    "香港副学士 申请 2025 2026 最新",
    # === 海外升学 ===
    "港籍生 英国 澳洲 新加坡 升学 最新",
    "DSE 海外大学 认可 最新名单",
    # === 港校招生（新增）===
    "港理工 招生 2025 最新",
    "港城大 招生 2025 最新",
    "港大 港中文 港科大 录取 2025",
    "港校 联招 取录 港生 内地生",
    "香港大学 专业 收生 要求 最新",
    "港校 跨学科 课程 招生",
    "港八大 学额 竞争 最新数据",
    # === 定向抓取港媒教育新闻（site:限定）===
    "site:mingpao.com 教育 DSE 2025",
    "site:mingpao.com 教育 港大 港理工 招生",
    "site:mingpao.com 教育 联招 JUPAS",
    "site:hk01.com 教育 DSE 2025 2026",
    "site:hk01.com 教育 港校 录取 招生",
    "site:stheadline.com 教育 DSE 港校",
    "site:stheadline.com 教育 联招 收生",
    "site:tkww.hk 教育 港籍生 升学",
    "site:wenweipo.com 教育 DSE 港校",
    "site:dotdotnews.com 教育 港校 招生",
    "site:rthk.hk 教育 DSE 港校 2025",
]


# ==================== 新闻网站 RSS 订阅源 ====================
NEWS_SITES = [
    {"name": "明报教育", "url": "https://news.mingpao.com/rss/pns/s00011.xml", "type": "rss"},
    {"name": "南华早报", "url": "https://www.scmp.com/rss/2/feed", "type": "rss", "filter_edu": True},
    {
        "name": "文汇报",
        "url": "https://www.wenweipo.com/education",
        "type": "html",
        "parser": "wenweipo",
        "filter_edu": False,
    },
    {
        "name": "点新闻",
        "url": "https://www.dotdotnews.com/education",
        "type": "html",
        "parser": "dotdotnews",
        "filter_edu": False,
    },
]


# ==================== RSS 订阅源（独立RSS）====================
RSS_SOURCES = [
    {"name": "DSE00题库", "url": "https://www.dse00.com/feeds/posts/default?alt=rss", "category": "DSE"},
    {"name": "港大新闻", "url": "https://www.hku.hk/press/rss.xml", "category": "升学"},
    {
        "name": "RTHK中文本地",
        "url": "http://rthk.hk/rthk/news/rss/c_expressnews_clocal.xml",
        "category": "综合",
        "filter_edu": True,
    },
    {
        "name": "香港政府新闻处",
        "url": "http://www.news.gov.hk/rss/news/topstories_en.xml",
        "category": "综合",
        "filter_edu": True,
    },
]


# ==================== 微信公众号（通过搜狗搜索抓取）====================
WECHAT_ACCOUNTS = [
    "摘星DSE",
    "智优港DSE",
    "威学一百",
    "COURSEMO",
    "新航道深圳",
]


# ==================== 教育培训机构官网 ====================
EDU_SITES = [
    {"name": "唯寻教育", "url": "https://www.visionacademy.cn/", "type": "html"},
    {"name": "环球教育深圳", "url": "https://shenzhen.gedu.org/", "type": "html"},
    {"name": "犀牛教育", "url": "https://www.x-new.cn/", "type": "html"},
    {"name": "学为贵", "url": "https://www.guixue.com/", "type": "html"},
    {"name": "新东方深圳", "url": "https://www.xdf.cn/shenzhen/", "type": "html"},
    {"name": "金吉列", "url": "https://www.jjl.cn/", "type": "html"},
    {"name": "翰林", "url": "https://hanlin.com", "type": "html"},
    {"name": "超级学长", "url": "https://www.chaojixuezhang.com/", "type": "html"},
    {"name": "博明程", "url": "https://www.bmcedu.net/", "type": "html"},
    {"name": "LevelAlpha", "url": "https://www.levela.com.cn/", "type": "html"},
]


# ==================== 时效性配置 ====================
STALE_DAYS = 60
EXPIRED_DAYS = 180
TIME_WEIGHT_FACTOR = 0.3
