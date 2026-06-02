"""
爆款规律分析器
从样本文案中自动提取句式模板、钩子模板、CTA模板等
"""
import json
import re
from pathlib import Path
from typing import List, Dict


# 样本文案库（与 prompt_builder.py 保持一致）
SAMPLE_COPYWRITING = {
    "样本一": """今天咱们聊聊，孩子DSE考砸了，最差能去哪些大学？孩子如果英语过了3分，总分18分以上，港八大基本稳了！不过，这两年分数线卡在19分上下~ 好专业得22分以上才够得着
要是孩子英语合格，但总分不到18分，香港都会、树仁、恒生这几个可以保底，或者去澳门，澳门大学、澳科大，各科及格就有书读。最划算的，还是内地985大学！像武大、厦大这些学校，14分及以上+核心四科及格，就问题不大！
不过。要是孩子英语没到3分，但总分还可以！这种情况要么关注港校里的特长生通道，针对学科/科创/艺术体育类类拔尖的学生，每年都有名额。要么考个雅思6分或托福79分，替代DSE单科成绩，猛冲浸会大学。
另外，即使英语和总分都不理想，也别焦虑！有回乡证的，永居可以走暨南大学独立招生，5科12分就能录，英语2分也收，分还不够就先上预科班过渡一下。没回乡证的非永居，可以考虑香港副学士，六科全2分就能读，两年后再申港八！
最后，被很多家长忽略的一点，DSE分数除了港澳和内地，还能申海外啊！新加坡6所公办、英国TOP30都接受DSE成绩直申，澳洲八大，12分就能读。在规划升学路径的时候，打开思路，才能找到最合适的路！
关注我，让孩子不走弯路！""",
    "样本二": """2025年，港澳台侨全国联考，考试人数11882人，比2024年上涨了15%；DSE报考人数，是55,781人，相比2024年，增长了约10%。
这两种考试人数都在增长，内地生活的港籍家长比较纠结，到底选哪个更适合自家孩子？今天咱们基于考生的升学目标，用具体的录取数据对比一下这两种考试。
首先，如果孩子打算考取香港本地大学。
2024年，用DSE成绩考入港三的录取率是21.3%，港八的录取率为38.97%。这意味着，在DSE的考生中，前十分之二的学生可以进入香港大学、香港中文大学或者香港科技大学。约前十分之四的学生，能稳稳当当进香港八大。
而用联考成绩报港校，不是主流选择。上期视频介绍过港八对联考生的成绩要求，能达到的基本是前1%考生。考虑到港校要求联考学生，申请时同步提供雅思成绩。用联考成绩考取港八大，这难度比高考，甚至有过之无不及。
那如果孩子只考虑内地大学。
2024年，DSE考生，达到内地大学基本录取要求的人数，占比51.29%。达到清北入学要求的学生，约为1%。中游成绩的DSE永居考生，就有很大的希望入读内地中山大学、厦门大学，这个梯度的985院校。
而联考呢，2024年一万多人报名，内地只招5116人，本科录取率58.25%。清北录了10个，录取率千分之一，刚好比DSE困难10倍。想用联考成绩进985，录取率只有4.2%，比高考的3%高了一点点。
所以，对中上成绩的永居港宝来说，单看名校升学率，还是DSE更香一点。不过，最终决策还需要综合权衡孩子成绩、英语风险和经济成本。如果还是犹豫不决，后台留言，可领取黄金决策公式！
关注我，让孩子不走弯路！""",
    "样本三": """今年DSE的16位状元中，来自九龙民生书院的李政同学，以6科5**及数延（M2）5*的好成绩，毅然选择了香港城市大学的兽医学课程。
一些内地的港宝家长比较疑惑。状元怎么去了世界排名63的城大？去港大或中大不香吗？
港大或中大，确实香。但城大的兽医，也没那么简单！
首先，这个课程，是香港城大与全球排名第3的美国康奈尔大学兽医医学院联合开发的，全港头一个六年制的兽医学学士课程。主要研究动物福利、水产养殖动物健康、新发现传染病、食物健康这四大课题。包含12周的农场动物畜牧校外课程，跟26周的临床校外课程。
JUPAS的收生要求是，5科33.5；对内地高考生，要求英文单科不低于135，总分高出特控线80分及以上。
在读期间，有机会获得城大50万港币的Flagship奖学金，并去美国康奈尔大学交换。
毕业后，本港执业的话，起步月薪大概7到12万港币。当然，如果想寻求更多机会，去英国、美国、新西兰，或回中国内地，也都行。这个课程的毕业生，全球执业。
总结来说，别看城大排名一般，但这个课程，一点不一般。
其实，各位港宝家长，在规划升学目标的时候，不必紧盯着港大/中大那几个所谓「神科」。像城大兽医这种宝藏课程，还有很多，比如理大的放射学和眼科视光学、浸会的中医，也都「QIAN途无量」.
港校总共开了53个医学护理类课程，36个受港府资助，17个自资。部分课程的入学门槛不高，就业含金量却一点没打折，很适合普娃。
想要完整课程目录的港宝家长，欢迎留言或私询客服。
关注我，让孩子不走弯路！""",
    "样本四": """考完DSE ，估分和改志愿非常关键。接下来，你只有两次调整Jupas志愿的机会。
其一是5月27日下午五点之前，
其二是放榜后的7月16到18号。
放榜后时间短暂，要想科学、高效地改好志愿，这段时间，建议根据自己的模考成绩和考场表现，提前准备三套志愿方案，
放榜后可以直接套用：
第一套，超常发挥方案。以你的实际分数，比预估高出1-2 分为标准。"
    "这套方案的基本逻辑是，适当提高 A1 、 A2志愿的档次。"
    "比如原本你A1 填的是理大，此时可以改为科大，或者中大的相似专业；"
    " A2 志愿，可以选择一个录取难度稍高、同时你非常心仪的专业；"
    "至于A3 保底志愿，建议别动，确保稳妥。
第二套，正常发挥方案，以你的实际分数与估分一致为标准。结合之前计算的有效分，确定 BandA 三个志愿。 A2 确保能上，A1 留一点点冲刺空间，A3 非常稳妥；后续 17 个志愿，就按照"录取难度从高到低的排序，补充适配的专业即可。
第三套，分数偏低方案，以你的实际分数比估分低 1-2 分为标准。这种情况下，你需要依次调低BandA和Band B所有志愿。
把 A1 冲刺志愿，改为录取难度更低、单科门槛更宽松的专业；A2 志愿，则用原来的A3 保底志愿替换；至于A3 志愿，则进一步降低档次，尽量选择适配你成绩的，录取难度最低的专业。以确保不滑档为首要目标。
当然，各位同学和港宝家长，如果你对JUPAS志愿修改，仍然一头雾水。我们这边也提供一对一的JUPAS志愿修改服务，欢迎留言咨询。关注我，让孩子不走弯路。""",
    "样本五": """香港DSE数学包括必修部分和选修的延伸部分。延伸部分分为M1、M2两个单元。学生只能选修其中一个。
今天，我们聊聊，数学延伸单元M1、M2到底怎么选？
首先要明确，自己的目标院系是否要求必选M1/M2，港大、中大和科大的工科、计算机和商科这几个领域，很多课程都要求必选M1或M2，而文学、教育学、法学就没有这方面的强制要求。所以，如果目标院系有要求，肯定要选的。
再看目标学校的计分规则，对选修M1或M2的学生，是否有分数加乘，像港科大，在计算学生表现优秀的五科成绩时，M1或M2的成绩时双倍计算的，所以，数学还可以，且想要提升整体成绩的同学，就可以考虑一下。
最后是M1和M2的差异。
从学习内容和关联课程的角度，
M1适合喜欢统计、概率，且打算就读商科类统计学方向，或者社科领域心理学、政治学方向的学生。
M2则适合，对数字敏感、喜欢运算和研究数学原理，且打算就读金融、精算、工程、科技或数学相关领域的同学。
从得分率的角度，近五年，M1的3分率和5分率，都远低于M2。所以，选择M2，及格和拿高分的概率都远高于M1。
当然，每个孩子的情况不同，正在纠结的同学，如想确定选择M1或M2的可行性，还是要找资深老师，科学评估才行。
我们有许多毕业于top级名校，且DSE授课经验丰富的，港籍资深老师。
欢迎留言预约，让孩子不走弯路。""",
}


class ViralAnalyzer:
    """爆款文案规律分析器"""

    def __init__(self, patterns_path: str = "data/viral_patterns.json"):
        self.patterns_path = Path(patterns_path)
        self.patterns = self._load_or_analyze()

    def _load_or_analyze(self) -> Dict:
        if self.patterns_path.exists():
            with open(self.patterns_path, "r", encoding="utf-8") as f:
                return json.load(f)
        patterns = self.analyze_all()
        self._save(patterns)
        return patterns

    def _save(self, patterns: Dict):
        self.patterns_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.patterns_path, "w", encoding="utf-8") as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)

    def analyze_all(self) -> Dict:
        """分析所有样本文案，提取爆款规律"""
        return {
            "hook_patterns": self._extract_hooks(),
            "data_patterns": self._extract_data_patterns(),
            "cta_patterns": self._extract_cta(),
            "transition_words": self._extract_transitions(),
            "sentence_stats": self._analyze_sentences(),
            "emotion_flow": self._analyze_emotion_flow(),
        }

    def _extract_hooks(self) -> Dict[str, List[str]]:
        """提取钩子开场句式"""
        hooks = []
        for text in SAMPLE_COPYWRITING.values():
            lines = text.strip().split('\n')
            if lines:
                first = lines[0].strip()
                if len(first) > 10:
                    hooks.append(first)

        # 提取通用模板
        templates = [
            "今天咱们聊聊，{topic}",
            "{year}年，{event}，{data}",
            "{topic}，{question}",
            "{event}，{impact}",
        ]
        return {"examples": hooks, "templates": templates}

    def _extract_data_patterns(self) -> Dict[str, List[str]]:
        """提取数据呈现句式"""
        patterns = []
        for text in SAMPLE_COPYWRITING.values():
            # 匹配数据相关句子
            matches = re.findall(r'[^。\n]*(?:\d+[\.,]?\d*|百分之|上涨|增长|录取率|占比)[^。\n]*', text)
            for m in matches[:5]:
                m = m.strip()
                if len(m) > 5:
                    patterns.append(m)

        templates = [
            "{year}年，{event}，{number}人，比{compare_year}年上涨了{percent}%",
            "{event}的录取率是{percent}%",
            "{event}，占比{percent}%",
            "{number}人报名，{scope}只招{number2}人，本科录取率{percent}%",
        ]
        return {"examples": patterns[:10], "templates": templates}

    def _extract_cta(self) -> Dict[str, List[str]]:
        """提取行动号召句式"""
        ctas = []
        for text in SAMPLE_COPYWRITING.values():
            lines = text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if any(kw in line for kw in ["关注我", "留言", "私信", "咨询", "领取", "预约"]):
                    ctas.append(line)

        templates = [
            "关注我，让孩子不走弯路！",
            "想要{resource}的，欢迎{action}",
            "我们提供{service}，欢迎{action}",
            "{action}，让孩子不走弯路",
        ]
        return {"examples": list(set(ctas)), "templates": templates}

    def _extract_transitions(self) -> List[str]:
        """提取过渡词/句"""
        transitions = []
        for text in SAMPLE_COPYWRITING.values():
            # 提取段落开头词
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                for prefix in ["首先", "其次", "另外", "最后", "总结", "其实", "不过", "要是", "所以", "那如果", "再看"]:
                    if line.startswith(prefix):
                        transitions.append(prefix)

        return list(set(transitions))

    def _analyze_sentences(self) -> Dict:
        """分析句子长度和结构统计"""
        all_sentences = []
        for text in SAMPLE_COPYWRITING.values():
            sentences = re.split(r'[。\n]', text)
            for s in sentences:
                s = s.strip()
                if s:
                    all_sentences.append(s)

        lengths = [len(s) for s in all_sentences]
        return {
            "avg_length": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "min_length": min(lengths) if lengths else 0,
            "short_sentence_ratio": round(
                sum(1 for length in lengths if length <= 25) / len(lengths), 2
            ) if lengths else 0,
            "sample_count": len(all_sentences),
        }

    def _analyze_emotion_flow(self) -> List[str]:
        """分析情绪流动规律"""
        return [
            "钩子：制造悬念/焦虑（考砸了怎么办？）",
            "数据：用具体数字建立权威（11882人，录取率21.3%）",
            "分析：分层拆解，对比冲击（DSE vs 联考）",
            "转折：给出希望/解决方案（原来还有这条路）",
            "隐藏信息：制造信息差（很多家长不知道...）",
            "兜底：无论如何都有书读（消除焦虑）",
            "CTA：引导关注/互动/转化",
        ]

    def get_patterns(self) -> Dict:
        """获取所有爆款规律"""
        return self.patterns

    def format_for_prompt(self) -> str:
        """将爆款规律格式化为 Prompt 可用的文本"""
        p = self.patterns
        lines = [
            "=== 爆款文案规律分析（基于高点击样本文案） ===",
            "",
            "【钩子开场模板】",
        ]
        for t in p.get("hook_patterns", {}).get("templates", []):
            lines.append(f"  - {t}")

        lines.extend(["", "【数据呈现模板】"])
        for t in p.get("data_patterns", {}).get("templates", []):
            lines.append(f"  - {t}")

        lines.extend(["", "【CTA模板】"])
        for t in p.get("cta_patterns", {}).get("templates", []):
            lines.append(f"  - {t}")

        lines.extend(["", "【自然过渡词】"])
        lines.append(f"  {', '.join(p.get('transition_words', []))}")

        lines.extend(["", "【句子结构统计】"])
        stats = p.get("sentence_stats", {})
        lines.append(f"  平均句长: {stats.get('avg_length', 0)}字")
        lines.append(f"  短句占比(≤25字): {stats.get('short_sentence_ratio', 0) * 100:.0f}%")

        lines.extend(["", "【情绪流动公式】"])
        for i, step in enumerate(p.get("emotion_flow", []), 1):
            lines.append(f"  {i}. {step}")

        return "\n".join(lines)


def get_viral_patterns() -> Dict:
    """便捷函数"""
    analyzer = ViralAnalyzer()
    return analyzer.get_patterns()
