"""Strategy endpoints — CRUD and version management."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_strategies():
    return {"code": 0, "data": []}


@router.post("")
async def create_strategy():
    return {"code": 0, "data": {}}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    return {"code": 0, "data": {}}


@router.put("/{strategy_id}")
async def update_strategy(strategy_id: str):
    return {"code": 0, "data": {}}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    return {"code": 0, "message": "deleted"}
