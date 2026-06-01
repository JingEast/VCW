"""
精修工作流模块
保存精修版本、版本对比、一键去 AI 味优化
"""
import logging
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# 去 AI 味优化指令
DEO_AI_PROMPT = """你是一位资深短视频文案编辑，擅长将AI生成的文案润色为真人博主的口语表达。

请对以下文案进行"去AI味"精修，要求：
1. 打破完美逻辑——加入一些口语停顿、自我修正、重复强调
2. 长短句交错——不要用整齐的排比，让句子长短不一
3. 情绪化表达——该惊叹的地方用"哇""天哪""说实话"等感叹
4. 人称拉近——多用"咱们""你家孩子""各位家长"拉近距离
5. 去学术化——把"因此""综上所述"换成"说白了""老实说""说句掏心窝的话"
6. 加入不完美的真实感——偶尔说"这个...""那个...""我直说了啊"

注意：保留所有核心数据和政策信息，只修改表达方式。精修后的文案要能直接对着镜头读出来。

【原文案】
{content}

请直接输出精修后的文案，不要加任何解释。"""


class EditorWorkflow:
    """精修工作流"""
    
    def __init__(self, edit_dir: str = "data/edited"):
        self.edit_dir = Path(edit_dir)
        self.edit_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.edit_dir / "index.json"
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger = logging.getLogger(__name__)
                logger.warning("Editor index corrupted (%s), starting fresh", exc)
                return {"versions": []}
        return {"versions": []}
    
    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def save_draft(self, original_content: str, topic: str,
                   source_filepath: str = "", meta: str = "") -> str:
        """
        保存原始文案为可精修草稿
        
        Returns:
            draft_id
        """
        draft_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        draft = {
            "id": draft_id,
            "topic": topic,
            "source_filepath": source_filepath,
            "meta": meta,
            "original": original_content,
            "edited": original_content,
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "edit_history": [],
        }
        
        self.index["versions"].append(draft)
        self._save_index()
        
        # 同时保存为 markdown 文件
        self._save_markdown(draft)
        
        return draft_id
    
    def update_edited(self, draft_id: str, edited_content: str,
                      edit_note: str = "") -> bool:
        """更新精修内容"""
        for v in self.index["versions"]:
            if v["id"] == draft_id:
                # 记录编辑历史
                v["edit_history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "note": edit_note,
                    "before_length": len(v["edited"]),
                    "after_length": len(edited_content),
                })
                
                v["edited"] = edited_content
                v["updated_at"] = datetime.now().isoformat()
                v["status"] = "edited"
                
                self._save_index()
                self._save_markdown(v)
                return True
        return False
    
    def finalize(self, draft_id: str) -> bool:
        """标记为最终版本"""
        for v in self.index["versions"]:
            if v["id"] == draft_id:
                v["status"] = "final"
                v["updated_at"] = datetime.now().isoformat()
                self._save_index()
                return True
        return False
    
    def get_draft(self, draft_id: str) -> Optional[Dict]:
        """获取草稿"""
        for v in self.index["versions"]:
            if v["id"] == draft_id:
                return v
        return None
    
    def get_all_drafts(self, status: str = None) -> List[Dict]:
        """获取所有草稿"""
        drafts = self.index["versions"]
        if status:
            drafts = [d for d in drafts if d.get("status") == status]
        return sorted(drafts, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def get_diff(self, draft_id: str) -> Tuple[str, str]:
        """获取原始版 vs 精修版的对比"""
        draft = self.get_draft(draft_id)
        if not draft:
            return "", ""
        return draft.get("original", ""), draft.get("edited", "")
    
    def build_de_ai_prompt(self, content: str) -> str:
        """构建去 AI 味的优化提示词"""
        return DEO_AI_PROMPT.format(content=content)
    
    def _save_markdown(self, draft: Dict):
        """保存为 markdown 文件"""
        safe_topic = re.sub(r'[^\w\u4e00-\u9fff]', '_', draft.get("topic", "untitled"))[:30]
        filename = f"{draft['id']}_{safe_topic}.md"
        filepath = self.edit_dir / filename
        
        header = f"""---
draft_id: {draft['id']}
topic: {draft.get('topic', '')}
status: {draft.get('status', '')}
created_at: {draft.get('created_at', '')}
updated_at: {draft.get('updated_at', '')}
---

# 原始文案

{draft.get('original', '')}

---

# 精修后文案

{draft.get('edited', '')}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header)
