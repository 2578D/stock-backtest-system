"""Strategy endpoints — CRUD and version management."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


class CreateStrategyRequest(BaseModel):
    name: str
    description: str | None = None
    type: str = "visual"        # "visual" | "code"
    rules_json: dict | None = None  # Visual strategy JSON rules
    code_content: str | None = None # Code strategy Python code
    market: str = "A股"
    period: str = "daily"
    risk_control: dict | None = None
    is_shared: bool = False


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    rules_json: dict | None = None
    code_content: str | None = None
    risk_control: dict | None = None
    is_shared: bool | None = None


@router.get("")
async def list_strategies(db: AsyncSession = Depends(get_db)):
    """List all strategies."""
    result = await db.execute(
        text(
            """SELECT id, name, description, type, market, period,
            is_shared, version, created_at, updated_at
            FROM strategy ORDER BY updated_at DESC LIMIT 50"""
        )
    )
    rows = result.fetchall()
    return {
        "code": 0,
        "data": [
            {
                "id": str(r[0]),
                "name": r[1],
                "description": r[2],
                "type": r[3],
                "market": r[4],
                "period": r[5],
                "is_shared": r[6],
                "version": r[7],
                "created_at": str(r[8]) if r[8] else None,
                "updated_at": str(r[9]) if r[9] else None,
            }
            for r in rows
        ],
    }


@router.post("")
async def create_strategy(
    req: CreateStrategyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new strategy."""
    sid = str(uuid.uuid4())
    await db.execute(
        text(
            """INSERT INTO strategy
            (id, user_id, name, description, type, rules_json, code_content,
             market, period, risk_control, is_shared)
            VALUES (CAST(:id AS UUID), CAST(:uid AS UUID), :name, :desc, :type,
             CAST(:rules AS JSONB), :code, :market, :period,
             CAST(:risk AS JSONB), :shared)"""
        ),
        {
            "id": sid,
            "uid": "00000000-0000-0000-0000-000000000000",
            "name": req.name,
            "desc": req.description,
            "type": req.type,
            "rules": json.dumps(req.rules_json) if req.rules_json else "{}",
            "code": req.code_content,
            "market": req.market,
            "period": req.period,
            "risk": json.dumps(req.risk_control) if req.risk_control else "{}",
            "shared": req.is_shared,
        },
    )
    await db.commit()
    return {"code": 0, "data": {"id": sid}}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Get full strategy details including rules/code."""
    result = await db.execute(
        text(
            """SELECT id, name, description, type, rules_json, code_content,
            market, period, risk_control, is_shared, version,
            created_at, updated_at
            FROM strategy WHERE id = CAST(:id AS UUID)"""
        ),
        {"id": strategy_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Strategy not found")

    return {
        "code": 0,
        "data": {
            "id": str(row[0]),
            "name": row[1],
            "description": row[2],
            "type": row[3],
            "rules_json": row[4],
            "code_content": row[5],
            "market": row[6],
            "period": row[7],
            "risk_control": row[8],
            "is_shared": row[9],
            "version": row[10],
            "created_at": str(row[11]) if row[11] else None,
            "updated_at": str(row[12]) if row[12] else None,
        },
    }


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    req: UpdateStrategyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update strategy fields."""
    sets = []
    params = {"id": strategy_id}

    if req.name is not None:
        sets.append("name = :name")
        params["name"] = req.name
    if req.description is not None:
        sets.append("description = :desc")
        params["desc"] = req.description
    if req.rules_json is not None:
        sets.append("rules_json = CAST(:rules AS JSONB)")
        params["rules"] = json.dumps(req.rules_json)
    if req.code_content is not None:
        sets.append("code_content = :code")
        params["code"] = req.code_content
    if req.risk_control is not None:
        sets.append("risk_control = CAST(:risk AS JSONB)")
        params["risk"] = json.dumps(req.risk_control)
    if req.is_shared is not None:
        sets.append("is_shared = :shared")
        params["shared"] = req.is_shared

    if sets:
        sets.append("version = version + 1")
        sets.append("updated_at = NOW()")
        await db.execute(
            text(
                f"UPDATE strategy SET {', '.join(sets)} WHERE id = CAST(:id AS UUID)"
            ),
            params,
        )
        await db.commit()

    return {"code": 0, "message": "updated"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a strategy."""
    await db.execute(
        text("DELETE FROM strategy WHERE id = CAST(:id AS UUID)"),
        {"id": strategy_id},
    )
    await db.commit()
    return {"code": 0, "message": "deleted"}
