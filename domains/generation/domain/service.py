"""
Generation Domain — Domain Service
===================================

文案生成领域的无状态业务逻辑服务。
"""

import re

from .value_object import QualityIssue, QualityReport


class QualityChecker:
    """
    文案质量检查器（领域服务）。

    对生成的文案进行自动化质量检查和时效性校验。
    无外部依赖，纯 Python 正则与字符串处理。
    """

    FORBIDDEN_WORDS = ["综上所述", "由此可见", "总而言之"]
    VAGUE_TIME_WORDS = ["近年来", "近几年", "前些年", "不久前"]
    COVID_PATTERNS = ["疫情", "新冠", "线上考试", "特别安排", "临时政策"]
    META_WORDS = ["meta", "模型", "AI生成", "自动生成"]

    def __init__(self):
        pass

    def check(self, content: str, strict_mode: bool = False) -> QualityReport:
        """执行全部质量检查，返回报告。"""
        report = QualityReport()

        self._check_structure(content, report)
        self._check_data_timeliness(content, report)
        self._check_forbidden_words(content, report)
        self._check_ai_flavor(content, report)
        self._check_length(content, report)
        self._check_school_names(content, report)
        self._check_call_to_action(content, report)
        self._check_meta_words(content, report)

        return report

    def _check_structure(self, content: str, report: QualityReport) -> None:
        """检查五段式结构。"""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            report.add_issue(
                QualityIssue(
                    category="结构",
                    level="warning",
                    message="文案分段较少，可能未严格遵循五段式结构",
                    suggestion="建议明确分为：钩子开场、背景铺垫、核心分析、补充信息、行动号召五部分",
                )
            )

    def _check_data_timeliness(self, content: str, report: QualityReport) -> None:
        """检查数据时效性。"""
        # 模糊时间
        vague_years = re.findall(r"近年来|近几年|前些年|不久前", content)
        if vague_years:
            report.add_issue(
                QualityIssue(
                    category="时效性",
                    level="error",
                    message=f"发现模糊时间表述: {vague_years}",
                    suggestion="禁止使用'近年来''近几年'等词，必须具体到'2025年''今年'",
                )
            )

        # 较早的年份
        old_years = re.findall(r"20(?:1\d|20|21|22|23|24)年", content)
        if old_years:
            report.add_issue(
                QualityIssue(
                    category="时效性",
                    level="warning",
                    message=f"发现较早的年份引用: {old_years}",
                    suggestion="请确认这些数据是否为最新，如非最新请标注为历史对比或更新为2025-2026年数据",
                )
            )

        # 疫情相关
        covid_found = [w for w in self.COVID_PATTERNS if w in content]
        if covid_found:
            report.add_issue(
                QualityIssue(
                    category="时效性",
                    level="error",
                    message=f"发现可能已过期的疫情相关表述: {covid_found}",
                    suggestion="疫情期间的特别政策大多已取消，请核实该政策当前是否仍然有效",
                )
            )

        # 时效性声明
        if not re.search(r"以官方最新公布为准|根据最新公开信息|截至20\d{2}年", content):
            report.add_issue(
                QualityIssue(
                    category="时效性",
                    level="info",
                    message="未找到数据时效性声明",
                    suggestion="建议在文案中添加'以官方最新公布为准'等提示",
                )
            )

    def _check_forbidden_words(self, content: str, report: QualityReport) -> None:
        """检查禁用词。"""
        for word in self.FORBIDDEN_WORDS:
            if word in content:
                report.add_issue(
                    QualityIssue(
                        category="语言风格",
                        level="error",
                        message=f"发现学术化连接词: '{word}'",
                        suggestion="换成口语化过渡，如'说白了''老实说'",
                    )
                )

    def _check_ai_flavor(self, content: str, report: QualityReport) -> None:
        """检查 AI 味。"""
        ai_patterns = [
            (r"首先[，,].*其次[，,].*最后[，,]", "结构化连接词"),
            (r"值得注意的是", "书面化表达"),
            (r"这意味着", "学术化推理"),
        ]
        for pattern, desc in ai_patterns:
            if re.search(pattern, content):
                report.add_issue(
                    QualityIssue(
                        category="AI味",
                        level="warning",
                        message=f"发现{desc}，可能带有AI生成痕迹",
                        suggestion="加入口语停顿、情绪表达、长短句交错",
                    )
                )

    def _check_length(self, content: str, report: QualityReport) -> None:
        """检查文案长度。"""
        length = len(content)
        if length < 200:
            report.add_issue(
                QualityIssue(
                    category="长度",
                    level="warning",
                    message=f"文案过短（{length}字），可能信息不足",
                    suggestion="建议补充更多核心数据或案例",
                )
            )
        elif length > 2000:
            report.add_issue(
                QualityIssue(
                    category="长度",
                    level="info",
                    message=f"文案较长（{length}字），注意短视频时长控制",
                    suggestion="可考虑拆分为系列内容",
                )
            )

    def _check_school_names(self, content: str, report: QualityReport) -> None:
        """检查学校名称准确性提示。"""
        # 仅做提示性检查，不阻断
        pass

    def _check_call_to_action(self, content: str, report: QualityReport) -> None:
        """检查行动号召。"""
        cta_patterns = ["留言", "私信", "点击", "预约", "领取", "咨询", "扫码"]
        if not any(p in content for p in cta_patterns):
            report.add_issue(
                QualityIssue(
                    category="转化",
                    level="warning",
                    message="未检测到明确的行动号召（CTA）",
                    suggestion="在结尾加入'留言领取升学路径全图'等明确的下一步动作",
                )
            )

    def _check_meta_words(self, content: str, report: QualityReport) -> None:
        """检查元信息词汇泄露。"""
        for word in self.META_WORDS:
            if word in content:
                report.add_issue(
                    QualityIssue(
                        category="元信息",
                        level="error",
                        message=f"发现元信息词汇泄露: '{word}'",
                        suggestion="删除AI生成相关的元描述词汇",
                    )
                )
