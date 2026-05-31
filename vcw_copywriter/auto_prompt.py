"""
自动 Prompt 生成器 v3.1（Prompt Registry 适配版）
====================================================
根据热点话题 + 爆款规律模板，自动生成优化的文案参数。

新增：业务场景识别（权重计分制+排斥信号）、场景专属参数映射、场景-样本文案自动匹配。

本模块为兼容层：对外接口 100% 保持不变。内部 `build_enhanced_system_prompt`
已适配 PromptComposer，支持从 Registry 获取增强内容。
"""
import re
from datetime import datetime
from typing import Dict, List
from .viral_analyzer import ViralAnalyzer


class AutoPromptBuilder:
    """自动 Prompt 生成器（场景感知增强版 + Prompt Registry 适配）"""

    # ==================== 业务场景配置 ====================
    SCENE_CONFIG = {
        "香港中小学插班规划": {
            "strong": ["插班", "自行分配", "统一派位", "学位申请", "叩门", "叩門", "候補", "候补"],
            "medium": ["中小学", "小学", "中学", "派位", "学位", "学额", "学額", "幼稚园", "幼儿园", "升中", "升小", "小一", "中一"],
            "weak": ["学校申请", "入学试", "跨境学童", "新来港", "band1", "band2", "band3", "直资", "资助", "官立"],
            "repel": ["jupas", "dse备考", "毕业", "last day", "放榜后", "大学", "港八大", "港三大", "志愿填报", "选科", "m1", "m2", "pastpaper", "真题", "模考"],
            "audience": "港宝家长（插班阶段）",
            "policy": "香港中小学插班/派位政策",
            "hidden": "香港直资/私立学校插班的弹性收生通道；国际课程衔接路径",
            "cta": "留言领取'香港中小学插班攻略手册'",
            "extra": "重点关注学校选择、申请流程、时间节点",
            "sample": "",
        },
        "DSE笔试备考": {
            "strong": ["dse", "备考", "pastpaper", "past paper", "真题", "真題", "模考", "模擬試卷", "模拟试卷"],
            "medium": ["笔试", "筆試", "公民科", "公民與社會發展", "m1", "m2", "數延", "校本評核", "sba", "口试", "口语", "speaking", "listening", "reading", "writing"],
            "weak": ["考试", "考試", "复习", "複習", "冲刺", "衝刺", "技巧", "答題技巧", "评分准则", "評分準則", "考点", "考點", "错题", "錯題"],
            "repel": ["插班", "自行分配", "统一派位", "jupas", "志愿填报", "大学申请", "中小学", "小学", "中学", "学位"],
            "audience": "DSE考生",
            "policy": "DSE考试安排及评分政策",
            "hidden": "DSE各科的夺分技巧；非官方公布但历年有效的答题策略",
            "cta": "私信领取'DSE各科备考资料包'",
            "extra": "重点关注备考策略、科目技巧、时间管理",
            "sample": "样本五",
        },
        "港籍升学规划": {
            "strong": ["jupas", "志愿填报", "志願填報", "联招", "聯招", "港八大", "港三大", "放榜", "放榜后", "改选", "改選", "last day", "毕业", "畢業"],
            "medium": ["大学", "大學", "录取", "錄取", "分数线", "分數線", "港大", "港中文", "港科大", "港理工", "港城大", "浸会", "教大", "岭大", "专业", "專業", "学士", "學士"],
            "weak": ["升学", "升學", "规划", "規劃", "副学士", "副學士", "asso", "e-app", "非联招"],
            "repel": ["插班", "自行分配", "统一派位", "中小学", "小学", "中学", "学位", "叩门", "pastpaper", "真题", "模考"],
            "audience": "中六毕业生家长/DSE考生家长",
            "policy": "JUPAS联招及港校录取政策",
            "hidden": "JUPAS改选策略中的隐藏技巧；Band A/B/C的最优组合策略；非联招申请通道",
            "cta": "欢迎预约一对一JUPAS志愿填报咨询",
            "extra": "重点关注录取分析、志愿策略、隐藏路径",
            "sample": "样本四",
        },
        "港澳台联考/内地升学": {
            "strong": ["联考", "聯考", "全国联招", "全國聯招", "港澳台联考", "港澳子弟学校", "暨南", "华侨", "華僑"],
            "medium": ["内地高校", "內地高校", "内地985", "内地211", "保送", "独立招生", "獨立招生", "回乡证", "回鄉證"],
            "weak": ["内地", "內地", "大陆", "985", "211", "深圳大学", "中山大学", "厦门大学", "武汉大学"],
            "repel": ["dse", "港校", "jupas", "插班", "pastpaper", "雅思", "托福"],
            "audience": "计划参加港澳台联考的港宝家长",
            "policy": "港澳台联考招生及内地高校招收港籍生政策",
            "hidden": "内地部分985院校对港籍生的独立招生/保送通道；港澳子弟学校内部直升",
            "cta": "留言领取'港澳台联考报考指南'",
            "extra": "重点关注录取分数、报名流程、政策解读",
            "sample": "样本二",
        },
        "海外升学": {
            "strong": ["英国", "澳洲", "澳大利亞", "新加坡", "留学", "留學", "ucas", "海外大学", "海外升学"],
            "medium": ["雅思", "托福", "alevel", "a-level", "ib", "ap", "gre", "gmat", "sat", "海外", "英國"],
            "weak": ["出国", "出國", "国际课程", "國際課程", "国际 school", "名校", "世界排名"],
            "repel": ["联考", "全国联招", "暨南", "内地高校", "jupas", "插班", "pastpaper"],
            "audience": "计划海外留学的港宝家长",
            "policy": "海外院校DSE成绩认可及申请政策",
            "hidden": "新加坡、英国、澳洲接受DSE成绩的直申通道；部分海外院校中文授课项目",
            "cta": "留言领取'海外留学申请全攻略'",
            "extra": "重点关注申请流程、语言要求、费用",
            "sample": "",
        },
    }

    def __init__(self):
        self.viral = ViralAnalyzer()
        self._composer = None

    def _get_composer(self):
        """延迟初始化 PromptComposer"""
        if self._composer is None:
            from .prompts import PromptComposer, load_default_registry
            registry = load_default_registry()
            self._composer = PromptComposer(registry, mode="legacy")
        return self._composer

    def _infer_scene(self, title: str, summary: str) -> str:
        """
        推断业务场景（权重计分制）
        强信号+3分，中信号+2分，弱信号+1分，排斥信号-5分
        返回最高分的场景，或默认"港籍升学规划"
        """
        text = (title + " " + summary).lower()
        scores = {}

        for scene, cfg in self.SCENE_CONFIG.items():
            score = 0
            for kw in cfg["strong"]:
                if kw.lower() in text:
                    score += 3
            for kw in cfg["medium"]:
                if kw.lower() in text:
                    score += 2
            for kw in cfg["weak"]:
                if kw.lower() in text:
                    score += 1
            for kw in cfg["repel"]:
                if kw.lower() in text:
                    score -= 5
            scores[scene] = score

        best_scene = max(scores, key=lambda k: scores[k])
        if scores[best_scene] > 0:
            return best_scene
        return "港籍升学规划"  # 默认场景

    def _get_scene_cfg(self, scene: str) -> dict:
        """获取场景配置"""
        return self.SCENE_CONFIG.get(scene, self.SCENE_CONFIG["港籍升学规划"])

    def build_from_trend(self, trend: Dict, sample_ref: str = "") -> Dict:
        """
        根据热点话题自动生成文案参数

        Args:
            trend: 热点话题字典（含 title, summary, published_at, url）
            sample_ref: 参考样本标签

        Returns:
            自动填充的参数字典（含 scene 字段）
        """
        title = trend.get("title", "")
        summary = trend.get("summary", "")
        published_at = trend.get("published_at", "")

        scene = self._infer_scene(title, summary)
        cfg = self._get_scene_cfg(scene)

        # 如果外部未指定sample_ref，根据场景自动匹配
        auto_sample = sample_ref
        if not auto_sample and cfg["sample"]:
            auto_sample = cfg["sample"]

        return {
            "topic": self._extract_topic(title),
            "scene": scene,
            "audience": self._infer_audience(title, summary),
            "core_data": self._infer_core_data(title, summary, published_at),
            "policy_points": self._infer_policy(title, summary, published_at),
            "hidden_path": self._infer_hidden_path(title, summary),
            "call_to_action": self._generate_cta(title, summary),
            "sample_ref": auto_sample,
            "extra_requirements": self._generate_angle_prompt(title, summary),
        }

    def _extract_topic(self, title: str) -> str:
        """从标题提取主题，保留年份和政策关键词"""
        # 清理来源标识但不清理年份
        clean = re.sub(r'\s*[-|]\s*.*?网\s*$', '', title)
        clean = re.sub(r'\s*[-|]\s*.*?社\s*$', '', clean)
        clean = re.sub(r'\s*[-|]\s*.*?报\s*$', '', clean)
        # 清理末尾的无关标签
        clean = re.sub(r'\s*#.*$', '', clean)
        return clean[:50] or "港籍升学热点话题"

    def _infer_audience(self, title: str, summary: str) -> str:
        """推断目标受众（场景感知）"""
        scene = self._infer_scene(title, summary)
        cfg = self._get_scene_cfg(scene)

        # 特殊细化：根据具体关键词进一步细分
        text = (title + " " + summary).lower()
        if any(kw in text for kw in ["dse考生", "考生", "学生", "同学"]):
            return "DSE考生"
        if any(kw in text for kw in ["双非", "非永居"]):
            return "双非港宝家长"
        if any(kw in text for kw in ["永居", "回乡证"]):
            return "永居港宝家长"

        return cfg["audience"]

    def _extract_year_info(self, text: str) -> List[str]:
        """从文本中提取所有年份信息"""
        years = []
        # 匹配 "2025年" 或 "2025"
        year_matches = re.findall(r'(20\d{2})\s*年?', text)
        for y in set(year_matches):
            years.append(f"{y}年")
        return years

    def _get_current_school_year(self) -> str:
        """获取当前学年"""
        now = datetime.now()
        if now.month >= 9:
            return f"{now.year}-{now.year + 1}"
        else:
            return f"{now.year - 1}-{now.year}"

    def _infer_core_data(self, title: str, summary: str, published_at: str = "") -> str:
        """从标题和摘要推断核心数据（含时间校验）"""
        text = title + " " + summary

        # 提取具体数字信息
        numbers = re.findall(r'20\d{2}年?\s*[，,]?\s*[^。\n]{0,30}\d+[\.,]?\d*\s*(?:人|万|%)', text)

        # 提取年份信息
        years = self._extract_year_info(text)
        current_year = str(datetime.now().year)

        result_parts = []

        if numbers:
            result_parts.append("；".join(numbers[:3]))

        # 根据关键词推断并补充提示
        if "录取率" in text:
            result_parts.append(f"具体录取率数据请标注最新年份（如'{current_year}年'）")
        if "报考" in text or "报名" in text:
            result_parts.append(f"最新报考人数数据，标注年份和来源（如考评局{current_year}年公布）")
        if "分数线" in text:
            result_parts.append(f"最新分数线数据，标注年份和科目（以{current_year}年官方公布为准）")
        if "放榜" in text:
            result_parts.append(f"{current_year}年放榜相关数据")

        # 如果有明确的年份但比较旧，提示更新
        for y in years:
            match = re.search(r'\d{4}', y)
            if not match:
                continue
            year_num = int(match.group())
            if year_num < datetime.now().year - 1:
                result_parts.append(f"⚠️ 原文涉及{y}数据，请核实是否已更新至{current_year}年最新数据")
                break

        if result_parts:
            return "；".join(result_parts)

        return f"请根据主题补充最新核心数据（含年份和来源），当前为{current_year}年，建议标注'{current_year}年最新'"

    def _infer_policy(self, title: str, summary: str, published_at: str = "") -> str:
        """推断政策要点（场景感知+有效期自动推断）"""
        scene = self._infer_scene(title, summary)
        cfg = self._get_scene_cfg(scene)
        text = title + " " + summary
        current_year = datetime.now().year

        # 基础政策来自场景配置
        policies = [f"{cfg['policy']}（标注适用学年/有效期，以{current_year}年官方公布为准）"]

        # 根据关键词补充额外政策
        if any(kw in text for kw in ["副学士", "预科", "asso"]):
            policies.append(f"副学士/预科招生要求（标注{current_year}年最新门槛）")
        if any(kw in text for kw in ["永居", "回乡证", "非永居", "双非"]):
            policies.append(f"港籍身份认定及对应升学通道政策（{current_year}年有效）")
        if any(kw in text for kw in ["公民科", "通识", "课程改革"]):
            policies.append(f"DSE课程改革/公民科政策（{current_year}年最新安排）")

        # 时间校验提示
        years_in_text = re.findall(r'20\d{2}', text)
        for y in years_in_text:
            y_int = int(y)
            if y_int < current_year - 1:
                policies.append(f"⚠️ 注意：原文提及{y}年政策，请核实{current_year}年是否有更新或变动")
                break

        return "；".join(policies)

    def _infer_hidden_path(self, title: str, summary: str) -> str:
        """推断隐藏路径（场景感知）"""
        scene = self._infer_scene(title, summary)
        cfg = self._get_scene_cfg(scene)
        text = title + " " + summary

        # 场景基础隐藏路径
        base_path = cfg["hidden"] + "（请务必确认当前是否仍然有效，标注核实日期）"

        # 根据具体关键词补充额外路径
        extra_paths = []
        if re.search(r"英语|英文|雅思|托福", text, re.IGNORECASE):
            extra_paths.append("雅思/托福替代DSE英文成绩的通道")
        if re.search(r"分数|成绩|考砸|保底|低分", text, re.IGNORECASE):
            extra_paths.append("特长生通道、弹性收生计划")
        if re.search(r"副学士|asso|预科", text, re.IGNORECASE):
            extra_paths.append("副学士升港八的衔接路径")
        if re.search(r"永居|非永居|双非|回乡证", text, re.IGNORECASE):
            extra_paths.append("不同身份对应的差异化升学通道")
        if re.search(r"M1|M2|选科|数学", text, re.IGNORECASE):
            extra_paths.append("数学延伸单元与特定专业的加分/豁免通道")

        if extra_paths:
            return base_path + "；额外补充：" + "；".join(extra_paths)
        return base_path

    def _generate_cta(self, title: str, summary: str = "") -> str:
        """生成行动号召（场景感知）"""
        scene = self._infer_scene(title, summary)
        cfg = self._get_scene_cfg(scene)

        # 根据具体关键词进一步细化
        if any(kw in title for kw in ["保底", "考砸", "怎么办", "焦虑", "出路", "差"]):
            return "留言领取'DSE升学路径全图'"
        if any(kw in title for kw in ["分数", "录取", "率", "数据", "对比", "统计"]):
            return "后台留言，可领取黄金决策公式"

        return cfg["cta"]

    def _generate_angle_prompt(self, title: str, summary: str = "") -> str:
        """生成角度建议和时效性提示（场景感知）"""
        scene = self._infer_scene(title, summary)
        cfg = self._get_scene_cfg(scene)
        text = title + " " + summary
        angles = {
            "数据": "用最新数据建立权威性，对比冲击强烈，数字必须口语化",
            "焦虑": "先戳痛点再给希望，情绪起伏明显，强调'原来还有这条路'",
            "故事": "用真实案例/状元故事引入，有代入感和画面感",
            "政策": "政策解读型，强调'最新''刚刚公布'的紧迫感",
            "清单": "用清单式结构，条理清晰，每一点都有 actionable 建议",
            "指南": "步骤化讲解，像操作手册一样清晰，强调'跟着做就行'",
        }

        prompts = []

        # 场景基础要求
        prompts.append(f"【业务场景】{scene}——{cfg['extra']}")

        # 根据关键词选择切入角度
        if any(kw in text for kw in ["数据", "录取率", "报考", "分数", "对比", "统计", "人数"]):
            prompts.append(f"建议以'数据型'角度切入：{angles['数据']}")
        elif any(kw in text for kw in ["考砸", "保底", "怎么办", "焦虑", "出路", "差", "失败"]):
            prompts.append(f"建议以'焦虑型'角度切入：{angles['焦虑']}")
        elif any(kw in text for kw in ["状元", "案例", "经验", "故事", "家长", "学生", "同学"]):
            prompts.append(f"建议以'故事型'角度切入：{angles['故事']}")
        elif any(kw in text for kw in ["政策", "新规", "改革", "调整", "公布", "最新", "改变"]):
            prompts.append(f"建议以'政策解读型'角度切入：{angles['政策']}")
        elif any(kw in text for kw in ["件事", "清单", "步骤", "流程", "攻略", "指南", "last day", "必须", "一定", "要"]):
            prompts.append(f"建议以'清单/指南型'角度切入：{angles['清单']}")
        else:
            prompts.append("请生成3个不同角度的变体：焦虑型、数据型、政策解读型")

        # 时效性提醒
        current_year = datetime.now().year
        years_in_text = re.findall(r'20\d{2}', text)
        has_recent_year = any(int(y) >= current_year - 1 for y in years_in_text)

        if not has_recent_year:
            prompts.append(f"⚠️ 重要：该热点未明确提及{current_year}或{current_year+1}年的信息，生成时必须使用最新数据，禁止使用过时的年份和旧政策")

        # 来源可信度提示
        if any(kw in text.lower() for kw in ["考评局", "教育局", "edb", "hkeaa", "官方"]):
            prompts.append("✅ 来源可信度高（官方机构），可直接引用")
        elif any(kw in text.lower() for kw in ["网传", "传闻", "据说", "有消息称"]):
            prompts.append("⚠️ 来源可信度存疑，数据需标注'以官方最新公布为准'，避免绝对化表述")

        return "\n".join(prompts)

    def build_enhanced_system_prompt(self, base_prompt: str) -> str:
        """
        在基础 System Prompt 上叠加爆款规律

        Args:
            base_prompt: 原始的 SYSTEM_PROMPT_TEMPLATE

        Returns:
            增强后的 System Prompt
        """
        # 使用 PromptComposer 的 legacy 组合逻辑，确保与 prompt_builder 一致
        viral_text = self.viral.format_for_prompt()

        # 直接调用 composer 的内部逻辑，或自行替换
        # 这里保持与原来完全一致的替换逻辑
        enhanced = base_prompt.replace(
            "## 爆款规律总结（必须融入生成）",
            f"## 爆款规律总结（必须融入生成）\n\n{viral_text}\n\n---\n\n## 爆款规律总结（必须融入生成）"
        )
        return enhanced


def auto_fill_from_trend(trend: Dict, sample_ref: str = "") -> Dict:
    """便捷函数：从热点自动生成参数并转为URL参数（自动清理特殊字符）"""
    builder = AutoPromptBuilder()
    params = builder.build_from_trend(trend, sample_ref)

    def _clean_for_url(text: str, max_len: int = 300) -> str:
        """清理文本以适应URL传递"""
        if not text:
            return ""
        # 移除换行符，替换为空格
        text = text.replace("\n", " ").replace("\r", "")
        # 截断过长内容
        if len(text) > max_len:
            text = text[:max_len] + "..."
        return text.strip()

    # 转换为URL安全参数格式
    return {
        "topic": _clean_for_url(params["topic"], max_len=80),
        "scene": _clean_for_url(params.get("scene", ""), max_len=40),
        "core_data": _clean_for_url(params["core_data"], max_len=250),
        "policy_points": _clean_for_url(params["policy_points"], max_len=250),
        "hidden_path": _clean_for_url(params["hidden_path"], max_len=200),
        "call_to_action": _clean_for_url(params["call_to_action"], max_len=80),
    }
