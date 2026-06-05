"""Pydantic Response Schemas.

Provides validated response structures for API documentation
and runtime validation.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """Standard successful API response."""
    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(default="ok", description="状态消息")
    data: Any = Field(default=None, description="响应数据")
    error: Optional[Any] = Field(default=None, description="错误信息（成功时为 null）")


class ErrorDetail(BaseModel):
    """Error detail structure."""
    code: str = Field(description="错误代码")
    message: str = Field(description="错误消息")
    details: Optional[Any] = Field(default=None, description="详细错误信息")


class ErrorResponse(BaseModel):
    """Standard error API response."""
    success: bool = Field(default=False, description="请求是否成功")
    message: str = Field(default="Error occurred", description="状态消息")
    data: Optional[Any] = Field(default=None, description="响应数据（错误时为 null）")
    error: ErrorDetail = Field(description="错误详情")


class PaginatedMeta(BaseModel):
    """Pagination metadata."""
    page: int = Field(default=1, description="当前页码")
    per_page: int = Field(default=20, description="每页数量")
    total: int = Field(default=0, description="总记录数")
    total_pages: int = Field(default=0, description="总页数")


class PaginatedResponse(ApiResponse):
    """Paginated list response."""
    meta: PaginatedMeta = Field(description="分页元数据")
