"""Unified API response model."""

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = None


class PaginationMeta(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0


class PaginatedResponse(APIResponse):
    pagination: PaginationMeta | None = None


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def paginated(
    data: Any,
    page: int,
    page_size: int,
    total: int,
    message: str = "success",
) -> dict:
    return {
        "code": 0,
        "message": message,
        "data": data,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


def error(code: int = -1, message: str = "error", data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}
