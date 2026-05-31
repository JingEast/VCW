"""
Repository 基类
提供通用的 CRUD 操作，所有实体 Repository 继承此类。
"""
from typing import TypeVar, Generic, List, Optional, Type
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """通用 Repository 基类"""

    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model

    def add(self, obj: T) -> T:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get_by_id(self, obj_id) -> Optional[T]:
        return self.session.query(self.model).filter_by(id=obj_id).first()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        return self.session.query(self.model).offset(offset).limit(limit).all()

    def delete(self, obj_id) -> bool:
        obj = self.get_by_id(obj_id)
        if obj:
            self.session.delete(obj)
            self.session.commit()
            return True
        return False

    def count(self) -> int:
        return self.session.query(self.model).count()
