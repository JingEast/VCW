"""
轻量向量检索模块（纯 Python，无外部依赖）
基于 TF-IDF + 余弦相似度的记忆库检索
"""
import math
import re
from typing import List, Dict, Tuple


class LightVectorSearch:
    """
    轻量向量检索器
    
    实现原理：
    1. 分词：提取 1-4 字 n-gram（适合中文短文本）
    2. 词频统计：计算每个文档的词频向量
    3. TF-IDF：词频 × 逆文档频率
    4. 余弦相似度：查询与文档的相似度
    """
    
    def __init__(self):
        self.documents: List[Dict] = []      # 原始文档
        self.vectors: List[Dict[str, float]] = []  # TF-IDF 向量
        self.idf: Dict[str, float] = {}      # 逆文档频率
        self.vocab: set = set()              # 词汇表
    
    def _tokenize(self, text: str) -> List[str]:
        """中文分词：提取 1-4 字 n-gram + 清洗"""
        text = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text.lower())
        chars = text.replace(' ', '')
        tokens = []
        # 单字
        for c in chars:
            if len(c.encode('utf-8')) >= 3:  # 中文字符
                tokens.append(c)
        # 2-4 字词组
        for n in range(2, 5):
            for i in range(len(chars) - n + 1):
                tokens.append(chars[i:i+n])
        # 英文单词
        tokens.extend(re.findall(r'[a-z]+', text.lower()))
        return tokens
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算词频（归一化）"""
        tf: Dict[str, float] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = len(tokens)
        if total > 0:
            for t in tf:
                tf[t] = tf[t] / total
        return tf
    
    def _compute_idf(self, all_tokens: List[List[str]]):
        """计算逆文档频率"""
        doc_count = len(all_tokens)
        if doc_count == 0:
            return
        
        df: Dict[str, int] = {}  # 文档频率
        for tokens in all_tokens:
            seen = set(tokens)
            for t in seen:
                df[t] = df.get(t, 0) + 1
        
        for t, freq in df.items():
            self.idf[t] = math.log(doc_count / (freq + 1)) + 1
            self.vocab.add(t)
    
    def build_index(self, documents: List[Dict], text_key: str = "text"):
        """
        构建索引
        
        Args:
            documents: 文档列表，每个元素是 dict，至少包含 text_key 字段
            text_key: 用于检索的文本字段名
        """
        self.documents = documents
        self.vectors = []
        self.idf = {}
        self.vocab = set()
        
        if not documents:
            return
        
        # 1. 分词
        all_tokens = []
        for doc in documents:
            text = doc.get(text_key, "")
            tokens = self._tokenize(text)
            all_tokens.append(tokens)
        
        # 2. 计算 IDF
        self._compute_idf(all_tokens)
        
        # 3. 计算 TF-IDF 向量
        for tokens in all_tokens:
            tf = self._compute_tf(tokens)
            vec = {}
            for t, tf_val in tf.items():
                if t in self.idf:
                    vec[t] = tf_val * self.idf[t]
            self.vectors.append(vec)
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """
        检索最相似的文档
        
        Returns:
            [(document, score), ...] 按相似度降序
        """
        if not self.vectors:
            return []
        
        # 查询向量化
        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)
        query_vec = {}
        for t, tf_val in query_tf.items():
            idf_val = self.idf.get(t, 0)
            query_vec[t] = tf_val * idf_val
        
        # 计算余弦相似度
        results = []
        for i, doc_vec in enumerate(self.vectors):
            score = self._cosine_similarity(query_vec, doc_vec)
            if score > 0:
                results.append((self.documents[i], score))
        
        # 排序取 TopK
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算两个稀疏向量的余弦相似度"""
        # 点积
        dot = 0.0
        for t, v1 in vec1.items():
            v2 = vec2.get(t, 0)
            dot += v1 * v2
        
        # 模长
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
