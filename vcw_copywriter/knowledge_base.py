"""
知识库模块
存储香港中小学插班规划、港籍学生升学规划和DSE笔试备考的权威资源、关键词、工作流程
"""
from typing import List, Dict


# ==================== 香港中小学插班规划 ====================

SCHOOL_TRANSFER_WEBSITES = [
    {"name": "香港教育局 - 学位分配系统", "url": "https://www.edb.gov.hk/sc/edu-system/primary-secondary/spa-systems/overview/index.html", "category": "插班政策"},
    {"name": "家庭与学校合作事宜委员会 - 小学概览", "url": "https://www.chsc.hk/primary/gb", "category": "学校信息"},
    {"name": "家庭与学校合作事宜委员会 - 中学概览", "url": "https://www.chsc.hk/secondary/sc", "category": "学校信息"},
    {"name": "香港教育局 - 学校搜索引擎", "url": "https://www.edb.gov.hk/", "category": "学校信息"},
    {"name": "香港政府电话簿（中小学板块）", "url": "https://tel.directory.gov.hk/", "category": "联系查询"},
    {"name": "香港私立学校议会", "url": "https://www.hkspa.edu.hk/", "category": "私立学校"},
    {"name": "香港教育局 - 课程发展议会", "url": "https://www.edb.gov.hk/sc/curriculum-development/index.html", "category": "课程政策"},
    {"name": "香港考试及评核局", "url": "https://www.hkeaa.edu.hk/tc/", "category": "考试信息"},
    {"name": "香港教育局 - 学位安排支援", "url": "https://www.edb.gov.hk/en/student-parents/placement-assistance/about-placement-assistance/faq.html", "category": "插班政策"},
    {"name": "香港政府一站通（教育板块）", "url": "https://www.gov.hk/sc/residents/education/primary-secondary/index.htm", "category": "综合资讯"},
    {"name": "香港教育局 - 特殊教育及融合教育(SENSE)", "url": "https://www.edb.gov.hk/", "category": "特殊教育"},
    {"name": "香港中小学学业评估资料库", "url": "https://www.sqa.edu.hk/", "category": "评估数据"},
]

SCHOOL_TRANSFER_KEYWORDS = [
    "香港中小學插班 政策", "香港中小學插班 申請時間", "香港中小學插班 資格要求",
    "香港中小學插班 流程", "香港中學插班 統一派位", "香港小學插班 自行分配學位",
    "香港中小學 剩餘學位", "香港官立中學 插班", "香港資助小學 插班名額",
    "香港直資中學 插班申請", "香港私立中小學 插班要求", "香港國際中學 插班考試",
    "香港某區中小學 插班", "香港中小學 插班公告", "香港跨境學童 中小學插班",
    "香港新來港兒童 插班支援", "香港特殊教育需求 中小學插班", "香港中小學插班考試 範圍",
    "香港中小學 課程大綱", "香港中小學 學業評估 樣題", "香港中學插班 英文考試",
    "香港小學插班 數學考點", "香港中小學 全港性系統評估", "香港中小學插班 申請材料",
    "香港中小學插班 報名方式", "香港中小學插班 面試要求", "香港中小學插班 學籍證明",
    "香港中小學插班 諮詢方式",
]

SCHOOL_TRANSFER_WORKFLOW = """【香港中小学插班规划服务 - 完整工作流程】

（1）获客阶段（核心：引流触达，建立信任）
- 引流推广：通过线上（升学社群、小红书/抖音/公众号）、线下（教育展会、家长分享会）输出插班干货
- 线索收集：收集家长信息（学生年级、目标区域/学校类型、插班时间、学生基础）
- 初步沟通：解答核心疑问（插班政策、名额、难度），提供免费初步评估
- 信任建立：分享成功案例、服务优势，增强专业性认可

（2）咨询转化阶段（核心：需求深挖，达成合作）
- 需求深挖：明确插班年级、目标区域（港岛/九龙/新界）、学校类型（官立/资助/直资/私立/国际）、时间节点
- 插班可行性评估：结合政策、学校规则、学生基础评估成功率
- 服务方案定制：个性化插班规划方案，明确服务内容、周期、费用、保障
- 签约合作：签订合同，建立服务专属群

（3）服务执行阶段（核心：落地推进，精准对接）
- 政策与学校调研：实时跟进最新政策、目标学校插班规则、报名时间、考试要求
- 材料准备指导：指导准备学籍证明、成绩证明、港籍证件、居住证明、推荐信等
- 报名实操指导：协助完成插班报名，跟进审核进度
- 插班备考辅导：制定针对性备考计划，提供学科辅导、面试辅导
- 学校对接与沟通：与目标学校招生办对接，同步进展
- 突发情况处理：及时调整方案，提供备选学校

（4）交付阶段（核心：完成插班，确认结果）
- 录取跟进：查询结果，协助完成录取确认、缴费注册
- 未录取应对：启动备选方案或补录
- 入学衔接指导：熟悉课程、准备入学物品、了解校规
- 服务交付确认：提交服务总结报告

（5）后续跟进阶段（核心：口碑维护，长期服务）
- 短期跟进：入学后1-3个月询问适应情况
- 长期维护：推送政策信息，建立长期信任
- 口碑运营：邀请分享体验，推荐亲友
"""


# ==================== DSE笔试备考指导 ====================

DSE_WEBSITES = [
    # 备考指导
    {"name": "香港考试及评核局", "url": "https://www.hkeaa.edu.hk/tc/", "category": "官方考试"},
    {"name": "Exampro DSE Learning Platform", "url": "https://exampro.com.hk/", "category": "备考平台"},
    {"name": "DSE00 题库网", "url": "https://www.dse00.com/", "category": "题库资源"},
    {"name": "Halo A+", "url": "https://www.halo-a.com/", "category": "备考平台"},
    {"name": "香港公共图书馆", "url": "https://www.hkpl.gov.hk/", "category": "图书资源"},
    {"name": "thinka AI 练习平台", "url": "https://www.thinka.edu.hk/", "category": "AI练习"},
    # 辅助课程与资料
    {"name": "DSE PP 资源库", "url": "https://dsepp.com/", "category": "pastpaper"},
    {"name": "DSE讲堂(DSE Info)", "url": "https://dseinfo.com/", "category": "课程资讯"},
    {"name": "小卒论坛(考生交流)", "url": "https://www.hkexams.com/", "category": "考生社区"},
    {"name": "中国语文课程网", "url": "https://www.chineseedu.hk/", "category": "中文专项"},
    {"name": "DSE100 题库网", "url": "https://www.dse100.com/", "category": "题库资源"},
    {"name": "学友社(Hok Yau Club)", "url": "https://www.hyc.org.hk/", "category": "升学支援"},
    {"name": "学友社学生网", "url": "https://www.student.hk/", "category": "学生平台"},
    # 获客相关
    {"name": "香港教育城", "url": "https://www.edcity.hk/", "category": "教育平台"},
    {"name": "香港升学中心", "url": "https://www.hkupg.com/", "category": "升学服务"},
    {"name": "香港国际学校协会(ISHK)", "url": "https://www.ishk.edu.hk/", "category": "国际学校"},
    # 服务交付
    {"name": "改卷易 EC Marking", "url": "https://ecmarking.com/", "category": "改卷工具"},
    {"name": "JUPAS 官网", "url": "https://www.jupas.edu.hk/tc", "category": "本地升学"},
    {"name": "香港学校发展与问责处", "url": "https://www.sqa.edu.hk/", "category": "学校评估"},
]

DSE_KEYWORDS = [
    "香港DSE 筆試 備考", "DSE筆試 考試大綱", "DSE筆試 評分準則", "DSE筆試 歷年真題",
    "DSE筆試 備考指南", "DSE筆試 考點梳理", "DSE筆試 模擬試卷", "DSE筆試 時間表",
    "DSE 4+2模式 筆試備考", "DSE筆試 答題技巧", "DSE中文 筆試 備考", "DSE中文 閱讀 答題技巧",
    "DSE中文 寫作 備考攻略", "DSE英文 筆試 備考", "DSE英文 閱讀 真題解析",
    "DSE英文 寫作 數據類模板", "DSE英文 聽力 備考技巧", "DSE數學 筆試 備考",
    "DSE數學 M1 筆試考點", "DSE數學 計算題 答題步驟", "DSE公民與社會發展 筆試 備考",
    "DSE公民科 專題報告 備考", "DSE公民科 筆試 考點總結", "DSE物理 筆試 備考",
    "DSE物理 實驗題 答題技巧", "DSE化學 筆試 考點梳理", "DSE生物 筆試 真題練習",
    "DSE經濟 筆試 答題模板", "DSE中國歷史 筆試 備考攻略", "DSE企業會計與商業概論 筆試 考點",
    "DSE視覺藝術 筆試 備考", "DSE筆試 弱點突破", "DSE筆試 錯題整理方法",
    "DSE筆試 專項訓練", "DSE筆試 答題時間分配", "DSE筆試 常考陷阱",
    "DSE筆試 考前衝刺備考", "DSE筆試 校本評核（SBA） 輔導",
    "DSE筆試 核心詞彙 積累", "DSE筆試 實驗題 誤差分析", "DSE筆試 邏輯論述 答題技巧",
]

DSE_WORKFLOW = """【DSE笔试备考指导 - 完整服务流程】

（1）获客阶段
- 多渠道引流：升学社群、小红书/抖音/公众号输出备考干货、真题解析、提分技巧
- 线索收集：记录学生年级、备考阶段、目标分数、薄弱科目、插班/备考时间
- 初步对接：解答DSE笔试难度、辅导优势、备考周期、收费标准
- 信任建立：分享提分案例、师资实力，提供免费基础测评
- 营销转化：低价体验课、免费模考、备考资料包引流

（2）咨询转化阶段
- 深度需求挖掘：备考阶段（基础/专项/冲刺）、目标分数、目标院校、薄弱科目、班型偏好
- 学业评估：全科测评，分析知识漏洞、应试短板，评估提分空间
- 个性化方案定制：课程设置、师资配置、辅导方式、服务周期、时间节点、收费标准
- 签约合作：签订合同，建立专属服务群

（3）服务执行阶段
- 师资匹配与课程搭建：匹配港籍名师/DSE高分导师，搭建分阶段课程体系
- 日常教学实施：聚焦各科考点，结合真题讲解知识点、应试技巧、答题模板
- 个性化辅导与答疑：一对一补弱辅导，课后答疑机制
- 模考演练与学情分析：每月1-2次全真模考，生成个性化模考报告
- 学情跟踪与反馈：记录出勤率、作业完成、模考成绩，定期提交学情报告
- 考纲与考情更新：实时跟进考评局最新考纲、命题趋势、评分标准

（4）交付阶段
- 考前冲刺辅导：聚焦高频考点、难点题型、易错点，强化答题技巧
- 考试相关协助：协助报名、准考证、行程规划、考前提醒
- 备考成果验收：查询成绩，对比初始测评，评估辅导效果
- 服务交付确认：提交服务总结报告，收集反馈

（5）后续维护阶段
- 短期支援：成绩公布后提供升学指导、志愿填报建议
- 长期维护：推送考情、备考干货、升学资讯
- 口碑运营：邀请分享体验，转介绍优惠
"""


# ==================== 港籍学生升学规划 ====================

HONG_KONG_STUDENT_WEBSITES = [
    # === 官方政策（第一优先级，时效性最强）===
    {"name": "香港教育局", "url": "https://www.edb.gov.hk/", "category": "官方政策"},
    {"name": "香港考试及评核局", "url": "https://www.hkeaa.edu.hk/tc/", "category": "考试信息"},
    {"name": "JUPAS 大学联合招生", "url": "https://www.jupas.edu.hk/tc", "category": "升学申请"},
    {"name": "内地高校面向港澳台招生", "url": "https://www.gatzs.com.cn/", "category": "内地升学"},
    {"name": "联招办 - 港澳台联考网", "url": "http://www.eeagd.edu.cn/lzks/", "category": "联考报名"},
    {"name": "中国留学网（教育部）", "url": "https://www.cscse.edu.cn/", "category": "学历认证"},
    # === 港校招生 ===
    {"name": "香港大学 admissions", "url": "https://admissions.hku.hk/", "category": "港校招生"},
    {"name": "香港中文大学 admissions", "url": "https://admission.cuhk.edu.hk/", "category": "港校招生"},
    {"name": "香港科技大学 admissions", "url": "https://join.hkust.edu.hk/", "category": "港校招生"},
    {"name": "香港理工大学 admissions", "url": "https://www.polyu.edu.hk/study/ug", "category": "港校招生"},
    {"name": "香港城市大学 admissions", "url": "https://www.cityu.edu.hk/admo/", "category": "港校招生"},
    {"name": "香港浸会大学 admissions", "url": "https://admissions.hkbu.edu.hk/", "category": "港校招生"},
    # === 内地高校港澳台招生 ===
    {"name": "暨南大学港澳台招生", "url": "https://zsb.jnu.edu.cn/", "category": "内地升学"},
    {"name": "华侨大学港澳台招生", "url": "https://zsc.hqu.edu.cn/", "category": "内地升学"},
    {"name": "中山大学港澳台招生", "url": "https://admission.sysu.edu.cn/", "category": "内地升学"},
    {"name": "深圳大学港澳台招生", "url": "https://zsb.szu.edu.cn/", "category": "内地升学"},
    {"name": "华南理工大学港澳台招生", "url": "https://admission.scut.edu.cn/", "category": "内地升学"},
    # === 新闻资讯（用于热点追踪）===
    {"name": "星岛日报教育", "url": "https://std.stheadline.com/daily/news-listing/%E6%95%99%E8%82%B2", "category": "新闻资讯"},
    {"name": "香港01教育", "url": "https://www.hk01.com/%E6%95%99%E8%82%B2", "category": "新闻资讯"},
    {"name": "大公文汇教育", "url": "https://www.tkww.hk/%E6%95%99%E8%82%B2", "category": "新闻资讯"},
    {"name": "明报教育", "url": "https://news.mingpao.com/ins/%E6%95%99%E8%82%B2", "category": "新闻资讯"},
    {"name": "点新闻教育", "url": "https://www.dotdotnews.com/education", "category": "新闻资讯"},
    {"name": "文汇报教育", "url": "https://www.wenweipo.com/education", "category": "新闻资讯"},
]

HONG_KONG_STUDENT_KEYWORDS = [
    "港籍學生 升學規劃", "港寶 升學路徑", "港籍生 內地升學", "港籍生 香港升學",
    "DSE 升學規劃", "港澳台聯考 升學", "JUPAS 升學 港籍生", "港籍生 副學士",
    "港八大 錄取率 港籍生", "內地985 港籍招生", "內地211 港籍招生", "港籍生 清北升學",
    "港籍身份 升學優勢", "回鄉證 升學用途", "永居港寶 升學路徑", "非永居港寶 升學",
    "港籍生 海外升學", "港籍生 英國升學", "港籍生 澳洲升學", "港籍生 新加坡升學",
    "港寶家長 升學焦慮", "港寶家長 升學規劃", "雙非港寶 升學", "跨境學童 升學",
    "港籍生 升學時間規劃", "港籍生 學業評估", "港籍生 選科策略", "港籍生 志願填報",
    "港籍生 保底路徑", "港籍生 逆襲升學", "港籍生 分數線 對比", "港籍生 錄取數據",
    "港籍生 升學諮詢", "港籍生 一對一規劃", "港籍生 升學講座", "港籍生 成功案例",
    "港籍生 升學政策 2025", "港籍生 升學政策 2026", "港籍生 最新升學資訊",
    "港籍生 升學政策 2025年最新", "港籍生 升學政策 2026年最新",
    "DSE 2025 最新政策", "DSE 2026 最新政策", "DSE 放榜 2025", "DSE 放榜 2026",
    "港澳台联考 2025 报名", "港澳台联考 2026 报名",
    "内地高校 招收港籍生 2025 最新", "内地高校 招收港籍生 2026 最新",
    "香港中小学插班 2025 最新", "香港中小学插班 2026 最新",
    "港八大 录取 2025 最新数据", "港八大 录取 2026 最新数据",
    "JUPAS 2025 改选", "JUPAS 2026 改选", "JUPAS 志愿填报 2025", "JUPAS 志愿填报 2026",
    # 用户补充关键词
    "港籍升學 政策", "港籍升學 路徑", "港籍學生 升學資格", "港籍升學 時間表",
    "港籍升學 資助/獎學金", "港籍學生 內地高校 報名", "全國聯招 港籍 報名條件",
    "HKDSE 內地高校 錄取標準", "港籍 內地高校 申請材料", "港籍 內地大學 錄取結果",
    "港籍跨境生 內地升學", "港籍 香港高校 插班", "JUPAS 港籍 報名流程",
    "HKDSE 考試 時間表", "香港大學 港籍 錄取要求", "E-APP 港籍 報名指南",
    "香港專上課程 港籍申請", "HKDSE 考試範圍", "港籍升學 備考指南",
    "HKDSE 成績查詢", "港籍升學 學術競賽", "港籍 升學面試要求",
    "双非港宝", "永居", "临时身份",
]

HONG_KONG_STUDENT_WORKFLOW = """【港籍学生升学规划服务 - 完整服务流程】

（1）获客阶段（核心：精准触达，建立专业信任）
- 引流推广：通过小红书/抖音/公众号输出港籍升学干货（DSE vs 联考对比、港八大录取数据、内地985港籍招生政策）
- 线索收集：收集家长信息（学生年级、港籍身份状态、目标升学方向、当前学业水平）
- 初步沟通：解答核心疑问（港籍生有哪些升学通道？DSE和联考怎么选？内地高校对港籍生的录取要求）
- 信任建立：分享港籍生升学成功案例、港八大/内地985录取数据，提供免费升学潜力评估

（2）咨询转化阶段（核心：需求深挖，定制方案）
- 需求深挖：明确学生港籍身份（永居/非永居/有无回乡证）、目标升学区域（香港/内地/海外）、目标院校层次
- 升学通道评估：结合学生成绩、身份条件，评估DSE、港澳台联考、内地独立招生、JUPAS等各通道的可行性
- 个性化方案定制：制定专属升学规划方案，明确各阶段目标、时间节点、备考策略、备选路径
- 签约合作：签订服务合同，建立专属服务群，正式启动升学规划服务

（3）服务执行阶段（核心：全程跟进，精准落地）
- 学业评估与定位：全面评估学生学业水平，明确目标院校范围，制定分阶段提分计划
- 升学通道规划：根据学生条件和目标，确定主申通道和备选通道（DSE+联考双轨等）
- 备考辅导支持：提供DSE/联考各科备考辅导、答题技巧、模拟训练
- 申请实操指导：协助完成JUPAS报名、内地高校报名、材料准备、面试辅导
- 政策动态跟进：实时跟进港籍生升学最新政策（内地高校招生名额变动、DSE改革等）
- 进度跟踪反馈：定期向家长提交升学规划进度报告，及时调整策略

（4）交付阶段（核心：达成升学目标，完成录取）
- 录取跟进：跟踪各通道录取结果，协助确认录取、缴纳留位费
- 未录取应对：启动备选方案（补录、调剂、转申其他通道）
- 入学衔接指导：指导学生做好入学准备，熟悉新学校课程体系
- 服务交付确认：提交升学规划总结报告，确认服务完成

（5）后续维护阶段（核心：长期陪伴，口碑运营）
- 短期跟进：入学后定期询问适应情况，协助解决学业衔接问题
- 长期维护：推送港籍生各阶段升学资讯（中学→大学→研究生）
- 口碑运营：邀请家长分享升学规划体验，推荐有需求的亲友
"""


# ==================== 便捷函数 ====================

def get_all_keywords() -> List[str]:
    """获取所有业务线的关键词（用于热点爬虫）"""
    return SCHOOL_TRANSFER_KEYWORDS + DSE_KEYWORDS + HONG_KONG_STUDENT_KEYWORDS


def get_all_websites() -> List[Dict]:
    """获取所有权威网站"""
    return SCHOOL_TRANSFER_WEBSITES + DSE_WEBSITES + HONG_KONG_STUDENT_WEBSITES


def format_for_prompt(business_line: str = "all") -> str:
    """将知识库格式化为 Prompt 可用的文本"""
    lines = []
    
    if business_line in ("all", "插班"):
        lines.extend([
            "=== 香港中小学插班规划 - 权威资源 ===",
            "",
            "【权威网站】",
        ])
        for site in SCHOOL_TRANSFER_WEBSITES:
            lines.append(f"  - {site['name']} ({site['category']}): {site['url']}")
        
        lines.extend(["", "【服务流程】", SCHOOL_TRANSFER_WORKFLOW])
    
    if business_line in ("all", "DSE"):
        lines.extend([
            "",
            "=== DSE笔试备考指导 - 权威资源 ===",
            "",
            "【权威网站】",
        ])
        for site in DSE_WEBSITES:
            lines.append(f"  - {site['name']} ({site['category']}): {site['url']}")
        
        lines.extend(["", "【服务流程】", DSE_WORKFLOW])
    
    return "\n".join(lines)


# ==================== 实时信息源配置（用于爬虫）====================

NEWS_RSS_SOURCES = [
    # 注意：以下URL可能需要根据实际可用性调整
    {"name": "香港教育局新闻", "url": "https://www.edb.gov.hk/tc/about-edb/press/press-rss.html", "category": "政策"},
    {"name": "考评局新闻", "url": "https://www.hkeaa.edu.hk/tc/about_hkeaa/press_releases/", "category": "考试"},
]

REALTIME_SEARCH_SOURCES = [
    "https://top.baidu.com/board?tab=education",
    "https://www.weibo.com/hot/search",
]

# 时效性判断参考
TIMELINESS_GUIDE = """
【信息时效性判断指南】

第一优先级（最可信，优先使用）：
- 香港教育局(edb.gov.hk) 官方发布
- 香港考评局(hkeaa.edu.hk) 官方数据
- 内地高校官方招生网站
- JUPAS官方公告

第二优先级（可信，需核对）：
- 星岛日报、香港01、明报、大公文汇等主流媒体报道
- 大学官方 admissions 页面

第三优先级（参考，需谨慎）：
- 教育论坛、家长社群讨论
- 自媒体文章（需交叉验证）

过时信息黑名单（严禁使用）：
- 2024年以前的分数线（除非做历史对比）
- 疫情期间的临时政策（如线上考试、特别安排）
- 已取消的招生计划或专业
- 已合并或更名的院校旧名称
"""


def get_rss_sources() -> List[Dict]:
    """获取RSS订阅源列表（用于热点爬虫）"""
    return NEWS_RSS_SOURCES


def get_timeliness_guide() -> str:
    """获取时效性判断指南"""
    return TIMELINESS_GUIDE
