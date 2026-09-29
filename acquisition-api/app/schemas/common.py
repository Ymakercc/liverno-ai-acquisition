"""通用响应结构。

前端 request.ts 约定：成功 {code:0, message, data}，失败 {code:"<业务码>", message}。
注意：分页字段名必须是 `list`（前端契约），因此此处统一用 typing.List 标注，
避免类体内 `list` 名字遮蔽内置类型。
"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


class PageResult(BaseModel, Generic[T]):
    list: List[T] = Field(default_factory=lambda: [])
    total: int = 0
    page: int = 1
    page_size: int = 20


def ok(data: T, message: str = "ok") -> ApiResponse[T]:
    return ApiResponse[T](code=0, message=message, data=data)
