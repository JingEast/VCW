"""
质量检查模块
对生成的文案进行自动化质量检查和时效性校验
"""
import re
from typing import List, Dict, Tuple


class QualityChecker:
    """文案质量检查器"""

    def __init__(self):
        self.issues = []

    def check_all(self, content: str, strict_mode: bool = False) -> Tuple[bool, List[Dict]]:
        """
        执行全部质量检查

        Returns:
            (passed: bool, issues: list)
        """
        self.issues = []

        # 执行各项检查
        self._check_structure(content)
        self._check_data_timeliness(content)
        self._check_forbidden_words(content)
        self._check_ai_flavor(content)
        self._check_length(content)
        self._check_school_names(content)
        self._check_call_to_action(content)
        self._check_meta_words(content)

        passed = len(self.issues) == 0 or (not strict_mode and all(i["level"] != "error" for i in self.issues))
        return passed, self.issues

    def _add_issue(self, category: str, level: str, message: str, suggestion: str = ""):
        self.issues.append({
            "category": category,
            "level": level,  # error, warning, info
            "message": message,
            "suggestion": suggestion
        })

    def _check_structure(self, content: str):
        """检查五段式结构"""
        # 检查是否有明显的分段
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if len(paragraphs) < 3:
            self._add_issue(
                "结构", "warning",
                "文案分段较少，可能未严格遵循五段式结构",
                "建议明确分为：钩子开场、背景铺垫、核心分析、补充信息、行动号召五部分"
            )

    def _check_data_timeliness(self, content: str):
        """检查数据时效性"""
        # 检查是否有模糊年份
        vague_years = re.findall(r'近年来|近几年|前些年|不久前', content)
        if vague_years:
            self._add_issue(
                "时效性", "error",
                f"发现模糊时间表述: {vague_years}",
                "禁止使用'近年来''近几年'等词，必须具体到'2025年''今年'"
            )

        # 检查是否有具体年份（2020-2024年可能已过时）
        old_years = re.findall(r'20(?:1\d|20|21|22|23|24)年', content)
        if old_years:
            self._add_issue(
                "时效性", "warning",
                f"发现较早的年份引用: {old_years}",
                "请确认这些数据是否为最新，如非最新请标注为历史对比或更新为2025-2026年数据"
            )

        # 检查是否有疫情相关表述（很可能已过期）
        covid_patterns = re.findall(r'疫情|新冠|线上考试|特别安排|临时政策', content)
        if covid_patterns:
            self._add_issue(
                "时效性", "error",
                f"发现可能已过期的疫情相关表述: {covid_patterns}",
                "疫情期间的特别政策大多已取消，请核实该政策当前是否仍然有效"
            )

        # 检查是否有"以官方最新公布为准"等限定语
        if not re.search(r'以官方最新公布为准|根据最新公开信息|截至20\d{2}年', content):
            self._add_issue(
                "时效性", "info",
                "未找到数据时效性声明",
                "建议在文案中添加'以官方最新公布为准'等提示"
            )

    def _check_forbidden_words(self, content: str):
        """检查禁用词"""
        forbidden = ["综上所述", "由此可见", "总而言之", "综上所述", "综上所述"]
        for word in forbidden:
            if word in content:
                self._add_issue(
                    "语言风格", "error",
                    f"发现学术化连接词: '{word}'",
                    "请替换为口语化表达，如'说白了''老实说'"
                )

    def _check_ai_flavor(self, content: str):
        """检查AI味"""
        ai_patterns = [
            ("首先.*其次.*再次.*最后", "机械排比"),
            ("不仅.*而且", "复杂从句"),
            ("虽然.*但是", "复杂从句"),
        ]
        for pattern, desc in ai_patterns:
            if re.search(pattern, content, re.DOTALL):
                self._add_issue(
                    "去AI味", "warning",
                    f"发现可能的AI化表达: {desc}",
                    "尝试拆分为更短的句子，增加口语化停顿"
                )

    def _check_length(self, content: str):
        """检查字数"""
        # 提取正文部分（去除markdown标记）
        text = re.sub(r'#+\s*', '', content)
        text = re.sub(r'\*\*|__|\[.*?\]|\(.*?\)', '', text)
        char_count = len(text.replace(' ', '').replace('\n', ''))

        if char_count < 400:
            self._add_issue(
                "字数", "warning",
                f"文案字数偏少（约{char_count}字），可能不足600字",
                "建议补充更多具体案例或数据"
            )
        elif char_count > 1200:
            self._add_issue(
                "字数", "info",
                f"文案字数较多（约{char_count}字），可能超过900字",
                "口播时长可能超过3分钟，建议精简"
            )

    def _check_school_names(self, content: str):
        """检查是否有具体学校名称"""
        # 常见港校和内地高校
        school_patterns = [
            r'港大|香港大学', r'中大|香港中文大学', r'科大|香港科技大学',
            r'理大|香港理工大学', r'城大|香港城市大学', r'浸大|香港浸会大学',
            r'岭大|香港岭南大学', r'教大|香港教育大学',
            r'清华|北京大学|复旦|上交|浙大|南大|中大\(广州\)|武大',
            r'暨南大学|华侨大学', r'英国.*?大学|澳洲.*?大学'
        ]

        found_schools = []
        for pattern in school_patterns:
            matches = re.findall(pattern, content)
            found_schools.extend(matches)

        if len(set(found_schools)) < 2:
            self._add_issue(
                "内容", "warning",
                f"具体学校名称较少（发现{len(set(found_schools))}个）",
                "建议至少提及3个以上具体学校或专业名称，增强可信度"
            )

    def _check_call_to_action(self, content: str):
        """检查是否有行动号召"""
        cta_patterns = ['关注我', '留言', '私信', '咨询', '领取', '扫码', '点击']
        has_cta = any(p in content for p in cta_patterns)
        if not has_cta:
            self._add_issue(
                "结构", "error",
                "未找到明确的行动号召（CTA）",
                "结尾必须包含引导关注/留言/私信/领资料的语句"
            )

    def _check_meta_words(self, content: str):
        """检查是否有元信息泄露"""
        meta_words = ['AI生成', '模型生成', '我是AI', '作为AI', '根据提示词']
        for word in meta_words:
            if word in content:
                self._add_issue(
                    "元信息", "error",
                    f"发现元信息泄露: '{word}'",
                    "严禁在文案中提及AI、模型、生成等概念"
                )

    def format_report(self, passed: bool, issues: List[Dict]) -> str:
        """格式化检查报告"""
        lines = ["=== 质量检查报告 ===", ""]
        lines.append(f"结果: {'[OK] 通过' if passed else '[FAIL] 未通过'}")
        lines.append(f"发现问题: {len(issues)}个")
        lines.append("")

        if not issues:
            lines.append("恭喜！未发现问题。")
        else:
            for i, issue in enumerate(issues, 1):
                emoji = {"error": "[ERR]", "warning": "[WARN]", "info": "[INFO]"}.get(issue["level"], "[?]")
                lines.append(f"{emoji} [{issue['level'].upper()}] {issue['category']} - {issue['message']}")
                if issue["suggestion"]:
                    lines.append(f"   建议: {issue['suggestion']}")
                lines.append("")

        return "\n".join(lines)


def check_and_report(content: str, strict_mode: bool = False) -> Tuple[bool, str]:
    """便捷函数：检查并返回报告"""
    checker = QualityChecker()
    passed, issues = checker.check_all(content, strict_mode)
    report = checker.format_report(passed, issues)
    return passed, report
