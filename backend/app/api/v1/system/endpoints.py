"""System endpoints — user profile, config."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/profile")
async def get_profile():
    return {"code": 0, "data": {}}


@router.put("/profile")
async def update_profile():
    return {"code": 0, "data": {}}


@router.get("/config")
async def get_system_config():
    return {"code": 0, "data": {}}
