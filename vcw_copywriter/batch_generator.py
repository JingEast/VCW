"""
批量生成器
支持一次生成多个角度变体，串行调用避免限流
"""
import time
from typing import List, Dict
from .generator import CopywriterGenerator
from .checker import check_and_report


# 三种文案角度预设
ANGLE_PRESETS = {
    "焦虑型": {
        "style_note": "以焦虑+希望公式切入，先戳家长痛点（考砸了怎么办？），再给解决方案。情绪起伏大，感叹号多，短句密集。",
        "hook_template": "很多家长不知道，{topic}，其实藏着大坑！",
    },
    "数据型": {
        "style_note": "以权威数据建立信任，用具体数字锚定观点。对比结构清晰（A vs B），数字口语化表达。",
        "hook_template": "{year}年，{topic}，最新数据公布了！",
    },
    "故事型": {
        "style_note": "用真实案例/具体人物故事引入，有代入感和画面感。从个体故事扩展到普遍规律。",
        "hook_template": "最近有个港宝家长跟我吐槽，{topic}，听完我沉默了...",
    },
}


class BatchGenerator:
    """批量文案生成器"""

    def __init__(self, llm_config: Dict):
        self.llm_config = llm_config
        self.generator = CopywriterGenerator(llm_config)

    def generate_batch(self, system_prompt: str, user_prompt: str,
                       angles: List[str] = None,
                       on_progress=None) -> List[Dict]:
        """
        批量生成文案变体

        Args:
            system_prompt: 系统提示词
            user_prompt: 基础用户提示词
            angles: 角度列表，如 ["焦虑型", "数据型", "故事型"]
            on_progress: 进度回调函数 (current, total, status)

        Returns:
            结果列表，每项包含 angle, content, meta, passed, issues
        """
        angles = angles or ["焦虑型", "数据型", "故事型"]
        results = []
        total = len(angles)

        for i, angle in enumerate(angles, 1):
            if on_progress:
                on_progress(i, total, f"正在生成 {angle} 文案...")

            # 为当前角度定制 user prompt
            angle_prompt = self._build_angle_prompt(user_prompt, angle)

            # 调用生成
            success, content, meta = self.generator.generate(
                system_prompt, angle_prompt
            )

            if success:
                # 质量检查
                passed, report = check_and_report(content, strict_mode=False)

                # 解析问题
                issues = []
                for line in report.split("\n"):
                    line = line.strip()
                    if line.startswith("[ERR]"):
                        issues.append({"level": "error", "text": line.replace("[ERR]", "").strip()})
                    elif line.startswith("[WARN]"):
                        issues.append({"level": "warning", "text": line.replace("[WARN]", "").strip()})

                results.append({
                    "angle": angle,
                    "success": True,
                    "content": content,
                    "meta": meta,
                    "passed": passed,
                    "issues": issues,
                })
            else:
                results.append({
                    "angle": angle,
                    "success": False,
                    "content": "",
                    "meta": meta,
                    "passed": False,
                    "issues": [{"level": "error", "text": meta}],
                })

            # 礼貌延迟，避免限流
            if i < total:
                time.sleep(1)

        if on_progress:
            on_progress(total, total, "批量生成完成！")

        return results

    def _build_angle_prompt(self, base_prompt: str, angle: str) -> str:
        """为特定角度构建定制化的 user prompt"""
        preset = ANGLE_PRESETS.get(angle, {})
        style_note = preset.get("style_note", "")

        angle_section = f"""
---

## 本次生成角度要求

【角度类型】{angle}
【风格要求】{style_note}

请确保本次生成的文案严格符合上述角度风格，与其他角度有明显差异。
"""
        return base_prompt + angle_section

    def save_batch(self, results: List[Dict], topic: str,
                   output_dir: str = "data/generated") -> List[str]:
        """保存批量生成结果"""
        filepaths = []
        for r in results:
            if r.get("success"):
                # 在文件名中标注角度
                safe_angle = r["angle"].replace("型", "")
                filepath = self.generator.save_generated(
                    content=r["content"],
                    topic=f"{topic}_{safe_angle}",
                    meta=r["meta"],
                    output_dir=output_dir
                )
                filepaths.append(filepath)
        return filepaths
