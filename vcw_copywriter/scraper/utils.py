"""
共享工具层
时间解析、相关度计算、URL 处理等纯函数工具，
不依赖 Provider 状态，可被任意模块复用。
"""
import re
import urllib.parse
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional


class TimeParser:
    """时间解析工具（原 _parse_datetime / _infer_date_from_text / _extract_publish_time_from_html）"""

    @staticmethod
    def parse_datetime(raw: str) -> Optional[datetime]:
        """解析多种日期格式，返回 naive datetime"""
        raw = raw.strip()
        if not raw:
            return None
        dt = None
        try:
            dt = parsedate_to_datetime(raw)
        except (ValueError, TypeError):
            pass
        if not dt:
            formats = [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M%z",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
                "%Y年%m月%d日",
            ]
            clean = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', raw)
            for fmt in formats:
                try:
                    dt = datetime.strptime(clean, fmt)
                    break
                except ValueError:
                    continue
        if dt and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt

    @classmethod
    def infer_date_from_text(cls, title: str, summary: str = "") -> Optional[datetime]:
        """从标题和摘要中推断文章发布时间。"""
        full_text = ((title or "") + " " + (summary or "")).strip()
        title_only = (title or "").strip()
        now = datetime.now()

        def _guard(dt: Optional[datetime]) -> Optional[datetime]:
            if dt and (dt - now).days > 7:
                return None
            return dt

        pub_patterns = [
            r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*[^\d]*?(?:发布|公布|出台|实施|生效)',
            r'(?:发布|公布|出台|实施|生效|定于).*?(20\d{2})\s*年\s*(\d{1,2})\s*月',
        ]
        for pattern in pub_patterns:
            m = re.search(pattern, full_text)
            if m:
                try:
                    year, month = int(m.group(1)), int(m.group(2))
                    if 2020 <= year <= now.year + 1 and 1 <= month <= 12:
                        return _guard(datetime(year, month, 15))
                except ValueError:
                    pass

        m = re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?', full_text)
        if m:
            try:
                return _guard(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))))
            except ValueError:
                pass

        m = re.search(r'(20\d{2})[-/]([01]?\d)[-/]([0123]?\d)(?:\D|$)', full_text)
        if m:
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return _guard(datetime(year, month, day))
            except ValueError:
                pass

        m = re.search(r'(?:^|\D)(20\d{2})([01]\d)([0123]\d)(?:\D|$)', full_text)
        if m:
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return _guard(datetime(year, month, day))
            except ValueError:
                pass

        m = re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月', full_text)
        if m:
            try:
                year, month = int(m.group(1)), int(m.group(2))
                if year == now.year and 1 <= month <= 12:
                    return _guard(datetime(year, month, 1))
            except ValueError:
                pass

        m = re.search(r'(今年|明年|去年)\s*(\d{1,2})\s*月', full_text)
        if m:
            ref, month = m.group(1), int(m.group(2))
            year = now.year if ref == "今年" else (now.year + 1 if ref == "明年" else now.year - 1)
            try:
                return _guard(datetime(year, month, 1))
            except ValueError:
                pass

        relative_patterns = [
            (r'(今日|今天)\s*(\d{1,2})\s*[:：]\s*(\d{1,2})', 0, None),
            (r'(昨日|昨天)\s*(\d{1,2})\s*[:：]\s*(\d{1,2})', -1, None),
            (r'(前天)\s*(\d{1,2})\s*[:：]\s*(\d{1,2})', -2, None),
        ]
        for pattern, day_offset, _ in relative_patterns:
            m = re.search(pattern, full_text)
            if m:
                try:
                    hour, minute = int(m.group(2)), int(m.group(3))
                    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if day_offset:
                        dt = dt + timedelta(days=day_offset)
                    return _guard(dt)
                except ValueError:
                    pass

        ago_match = re.search(r'(\d+)\s*小时前', full_text)
        if ago_match:
            try:
                hours = int(ago_match.group(1))
                dt = now - timedelta(hours=hours)
                return _guard(dt)
            except ValueError:
                pass
        ago_match = re.search(r'(\d+)\s*分钟前', full_text)
        if ago_match:
            try:
                minutes = int(ago_match.group(1))
                dt = now - timedelta(minutes=minutes)
                return _guard(dt)
            except ValueError:
                pass

        m = re.search(r'^(20\d{2})\D', title_only)
        if m:
            year = int(m.group(1))
            if year == now.year:
                return _guard(datetime(year, now.month, 1))
            elif year == now.year + 1:
                return _guard(datetime(year, 1, 1))

        m = re.search(r'(?:^|\D)(20\d{2})(?:\D|$)', full_text)
        if m:
            year = int(m.group(1))
            if year == now.year:
                return _guard(datetime(year, now.month, 1))
            elif year == now.year + 1:
                return _guard(datetime(year, 1, 1))

        return None

    @classmethod
    def extract_publish_time_from_html(cls, html: str, fallback: str = "") -> str:
        """从原始网页 HTML 中提取发布时间（收集所有候选，选择最精确的）"""
        if not html:
            return fallback

        candidates = []
        meta_patterns = [
            (r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']', 1),
            (r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time["\']', 1),
            (r'<meta[^>]*name=["\']publishdate["\'][^>]*content=["\']([^"\']+)["\']', 1),
            (r'<meta[^>]*name=["\']published_time["\'][^>]*content=["\']([^"\']+)["\']', 1),
            (r'<meta[^>]*name=["\']pubdate["\'][^>]*content=["\']([^"\']+)["\']', 1),
            (r'<meta[^>]*name=["\']weibo:article:update_at["\'][^>]*content=["\']([^"\']+)["\']', 1),
            (r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']weibo:article:update_at["\']', 1),
            (r'<time[^>]*datetime=["\']([^"\']+)["\']', 1),
            (r'<time[^>]*class=["\'][^"\']*publish-date[^"\']*["\'][^>]*>([^<]+)</time>', 1),
        ]

        for pattern, group in meta_patterns:
            for m in re.finditer(pattern, html, re.IGNORECASE):
                raw = m.group(group).strip()
                special_match = re.match(r'(\d{2})\.(\d{2}),(\d{4})', raw)
                if special_match:
                    try:
                        month, day, year = int(special_match.group(1)), int(special_match.group(2)), int(special_match.group(3))
                        candidates.append((datetime(year, month, day), 1))
                    except ValueError:
                        pass
                    continue
                parsed = cls.parse_datetime(raw)
                if parsed:
                    prec = 2 if parsed.hour != 0 or parsed.minute != 0 else 1
                    candidates.append((parsed, prec))

        cn_patterns = [
            (r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})\s*[:：]\s*(\d{1,2})', 3),
            (r'发布(?:时间|于)[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})\s*[:：]\s*(\d{1,2})', 3),
            (r'发布(?:时间|于)[：:]\s*(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', 3),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', 3),
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{1,2})', 3),
        ]
        for pattern, precision in cn_patterns:
            for m in re.finditer(pattern, html):
                try:
                    year, month, day, hour, minute = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
                    candidates.append((datetime(year, month, day, hour, minute), precision))
                except ValueError:
                    continue

        if candidates:
            candidates.sort(key=lambda x: (x[1], x[0]), reverse=True)
            return candidates[0][0].strftime("%Y-%m-%d %H:%M")

        return fallback

    @classmethod
    def extract_date_from_url(cls, url: str) -> Optional[datetime]:
        """从URL中提取日期（常见新闻网站URL模式）"""
        if not url:
            return None
        m = re.search(r'/(\d{4})/(\d{2})/(\d{2})(?:/|\.[^/]*)', url)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        m = re.search(r'/(\d{4})(\d{2})/(\d{2})(?:/|\.[^/]*)', url)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        m = re.search(r'/(\d{4})(\d{2})(\d{2})(?:/|\.[^/]*)', url)
        if m:
            try:
                y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= mth <= 12 and 1 <= d <= 31:
                    return datetime(y, mth, d)
            except ValueError:
                pass
        return None


class RelevanceCalculator:
    """相关度计算工具（原 _calc_relevance / _is_education_related）"""

    @staticmethod
    def calc_relevance(title: str, snippet: str) -> int:
        """计算话题与港籍升学领域的相关度分数 (0-100)"""
        score = 20
        keywords_high = [
            "DSE", "港籍", "港宝", "联考", "JUPAS", "副学士", "港八大",
            "暨南", "升学", "插班", "港澳台", "华侨", "考评局",
            "香港大学", "港中文", "港科大", "港理工", "港城大",
            "永居", "非永居", "回乡证", "双非", "跨境",
            "内地高校", "985", "211", "录取率", "分数线",
            "志愿", "备考", "M1", "M2", "公民科",
            "自行分配", "统一派位", "学友社", "dse00",
            "student.hk", "港生", "港校", "联招",
        ]
        keywords_medium = [
            "香港", "澳门", "内地", "录取", "报考", "报名",
            "考试", "招生", "学位", "学校", "中学", "小学",
            "教育", "政策", "改革", "最新", "2025", "2026",
            "幼稚园", "幼儿园", "学额", "叩门", "band",
        ]
        keywords_low = [
            "学生", "家长", "学习", "成绩", "老师", "课程",
        ]
        region_negative = [
            "台北", "台中", "高雄", "台南", "台湾",
            "新加坡教育部", "日本", "韩国", "马来西亚",
            "泰国", "菲律宾", "印尼", "越南", "印度",
            "gov.taipei", ".gov.tw", ".edu.sg", ".go.jp",
        ]

        text = (title + " " + snippet).lower()

        for neg in region_negative:
            if neg.lower() in text:
                score -= 25

        for kw in keywords_high:
            if kw.lower() in text:
                score += 12
        for kw in keywords_medium:
            if kw.lower() in text:
                score += 4
        for kw in keywords_low:
            if kw.lower() in text:
                score += 1

        current_year = str(datetime.now().year)
        next_year = str(datetime.now().year + 1)
        if current_year in title or next_year in title:
            score += 10

        return max(0, min(score, 100))

    @staticmethod
    def is_education_related(text: str) -> bool:
        """判断文本是否与教育相关（计分制：至少命中2个核心词，且不命中负面词）"""
        if not text:
            return False
        text_lower = text.lower()

        core_keywords = [
            "教育", "学校", "大学", "中学", "小学", "考试", "高考",
            "录取", "招生", "报名", "升学", "dse", "联考", "jupas",
            "志愿", "分数", "备考", "专业", "本科", "硕士", "学士",
            "学费", "奖学金", "毕业", "考研", "插班", "派位",
            "学位", "学额", "课程", "教学", "考评", "文凭",
            "校本", "评核", "口试", "笔试", "放榜",
            "雅思", "托福", "sat", "a-level", "alevel", "ib", "ap",
            "gre", "gmat", "留学", "出国", "国际课程", "国际 school",
            "amc", "竞赛", "奥数", "英语", "数学", "物理", "化学",
            "university", "school", "admission", "exam",
        ]

        strong_keywords = [
            "dse", "jupas", "港籍", "港宝", "港澳台", "联考",
            "插班", "副学士", "考评局", "教育局", "学友社",
            "student.hk", "dse00", "band 1", "band1", "自行分配",
            "统一派位", "跨境学童", "新来港", "非永居", "永居",
        ]

        negative_keywords = [
            "体育", "足球", "篮球", "娱乐", "明星", "八卦",
            "财经", "股票", "股市", "基金", "投资", "理财",
            "天气", "交通", "车祸", "火灾", "命案", "罪案",
            "地产", "楼市", "房价", "楼盘", "拍卖", "招标",
            "台北", "台中", "高雄", "台湾", "台南",
            "新加坡", "日本", "韩国", "马来西亚", "泰国",
            "菲律宾", "印尼", "越南", "印度",
        ]

        for neg in negative_keywords:
            if neg in text_lower:
                return False

        score = 0
        for kw in strong_keywords:
            if kw in text_lower:
                score += 2
        for kw in core_keywords:
            if kw in text_lower:
                score += 1

        return score >= 2


class UrlUtils:
    """URL 处理工具"""

    @staticmethod
    def extract_real_url(url: str) -> str:
        """从 DuckDuckGo 跳转链接中提取真实目标 URL"""
        if not url:
            return url
        if url.startswith("//"):
            url = "https:" + url
        if "duckduckgo.com/l/?" in url and "uddg=" in url:
            try:
                parsed = urllib.parse.urlparse(url)
                params = urllib.parse.parse_qs(parsed.query)
                if "uddg" in params:
                    real_url = urllib.parse.unquote(params["uddg"][0])
                    real_url = re.sub(r'[?&]utm_[^&]+', '', real_url)
                    real_url = re.sub(r'[?&]from=[^&]+', '', real_url)
                    return real_url
            except (KeyError, IndexError, ValueError):
                pass
        return url

    @staticmethod
    def normalize_url(url: str) -> str:
        """标准化URL用于去重（去除tracking参数）"""
        if not url:
            return ""
        url = re.sub(r'[?&](utm_|fbclid|gclid|ref|source)=([^&]*)', '', url)
        url = url.rstrip('?')
        return url

    @staticmethod
    def title_similarity(a: str, b: str) -> float:
        """简单计算两个标题的 2-gram 相似度"""
        if not a or not b:
            return 0.0

        def ngrams(s, n=2):
            s = re.sub(r'[^\u4e00-\u9fff\w]', '', s.lower())
            return set(s[i:i+n] for i in range(len(s)-n+1))

        ga = ngrams(a)
        gb = ngrams(b)
        if not ga or not gb:
            return 0.0

        intersection = len(ga & gb)
        union = len(ga | gb)
        return intersection / union if union > 0 else 0.0


def classify_category(title: str, summary: str = "") -> str:
    """分类功能已关闭，所有内容统一标记为未分类"""
    return "未分类"
