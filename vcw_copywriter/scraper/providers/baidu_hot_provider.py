"""
百度热搜 Provider
（当前已失效，保留接口兼容性）
"""
import re
import urllib.parse
from datetime import datetime
from typing import List, Dict

from ..base import BaseProvider
from ..utils import TimeParser, RelevanceCalculator, classify_category


class BaiduHotProvider(BaseProvider):
    """百度热搜教育类 Provider"""

    @property
    def name(self) -> str:
        return "百度热搜"

    def fetch(self) -> List[Dict]:
        """抓取百度热搜教育相关条目"""
        trends: List[Dict] = []
        try:
            url = "https://top.baidu.com/board?tab=education"
            html = self.http.fetch(url, timeout=15)
            if not html:
                return trends

            patterns = [
                r'"word":"([^"]+)"',
                r'class="[^"]*keyword[^"]*"[^>]*>([^<]+)</a>',
                r'data-keyword="([^"]+)"',
            ]

            seen = set()
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for word in matches:
                    word = word.strip()
                    if word and word not in seen and len(word) > 5:
                        seen.add(word)
                        if RelevanceCalculator.is_education_related(word):
                            inferred = TimeParser.infer_date_from_text(word)
                            published_at = inferred.strftime("%Y-%m-%d %H:%M") if inferred else ""

                            trends.append({
                                "title": word,
                                "summary": "",
                                "source": "百度热搜",
                                "url": f"https://www.baidu.com/s?wd={urllib.parse.quote(word)}",
                                "published_at": published_at,
                                "fetched_at": datetime.now().isoformat(),
                                "keyword": "",
                                "relevance_score": RelevanceCalculator.calc_relevance(word, ""),
                                "_time_source": "title_inference",
                            })

                            if len(trends) >= 20:
                                return trends
        except Exception as e:
            print(f"[BaiduHotProvider] 百度热搜抓取失败: {e}")

        for t in trends:
            t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))
        return trends
