"""Factor research API endpoints.

Endpoints:
- GET  /factors              — list factor definitions
- GET  /factors/{id}         — factor detail
- POST /factors/{id}/analyze  — trigger analysis
- GET  /factors/{id}/analysis — list analyses
- GET  /factors/{id}/analysis/{aid} — analysis detail
- GET  /factors/{id}/values  — query factor values
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.auth.deps import get_current_user
from app.engine.factor_engine import BUILTIN_FACTORS
from app.models.factor import FactorAnalysis, FactorDefinition, FactorValue
from app.models.user import User

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────

class FactorDefOut(BaseModel):
    id: str
    name: str
    label: str
    category: str
    description: str | None = None
    params: dict | None = None
    is_builtin: bool = True

    class Config:
        from_attributes = True


class AnalyzeRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    group_count: int = 10
    forward_days: int = 10


class AnalyzeResponse(BaseModel):
    task_id: str


class AnalysisOut(BaseModel):
    id: str
    factor_id: str
    start_date: str
    end_date: str
    group_count: int
    forward_days: int
    ic_mean: float | None = None
    ic_std: float | None = None
    icir: float | None = None
    ic_series: dict | None = None
    layer_returns: dict | None = None
    layer_cumulative: dict | None = None
    monotonicity: float | None = None
    status: str
    error_message: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class FactorValueOut(BaseModel):
    stock_code: str
    trade_date: str
    value: float | None
    rank_pct: float | None


# ── Seed built-in factors ────────────────────────────────────

def _seed_builtins(db: Session) -> None:
    for f in BUILTIN_FACTORS:
        existing = db.query(FactorDefinition).filter_by(name=f["name"]).first()
        if not existing:
            db.add(FactorDefinition(
                name=f["name"], label=f["label"], category=f["category"],
                description=f["description"], params=f["params"], is_builtin=True,
            ))
    db.commit()


# ── Endpoints ────────────────────────────────────────────────

@router.get("/", response_model=list[FactorDefOut])
def list_factors(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _seed_builtins(db)
    q = db.query(FactorDefinition)
    if category:
        q = q.filter(FactorDefinition.category == category)
    factors = q.order_by(FactorDefinition.category, FactorDefinition.name).all()
    return [
        FactorDefOut(
            id=str(f.id), name=f.name, label=f.label, category=f.category,
            description=f.description, params=f.params, is_builtin=f.is_builtin,
        )
        for f in factors
    ]


@router.get("/{factor_id}", response_model=FactorDefOut)
def get_factor(
    factor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _seed_builtins(db)
    f = db.query(FactorDefinition).filter(FactorDefinition.id == factor_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Factor not found")
    return FactorDefOut(
        id=str(f.id), name=f.name, label=f.label, category=f.category,
        description=f.description, params=f.params, is_builtin=f.is_builtin,
    )


@router.post("/{factor_id}/analyze", response_model=AnalyzeResponse)
def analyze_factor(
    factor_id: str,
    req: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _seed_builtins(db)
    factor = db.query(FactorDefinition).filter(FactorDefinition.id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")

    from app.tasks.factor_tasks import run_factor_analysis

    # Create analysis placeholder
    analysis = FactorAnalysis(
        id=uuid.uuid4(),
        factor_id=uuid.UUID(factor_id),
        start_date=date.fromisoformat(req.start_date),
        end_date=date.fromisoformat(req.end_date),
        group_count=req.group_count,
        forward_days=req.forward_days,
        status="pending",
    )
    db.add(analysis)
    db.commit()

    task = run_factor_analysis.delay(
        factor_name=factor.name,
        factor_id=str(factor.id),
        start_date=req.start_date,
        end_date=req.end_date,
        group_count=req.group_count,
        forward_days=req.forward_days,
    )
    # Update with task id
    db.execute(
        text("UPDATE factor_analysis SET status='running' WHERE id = :aid"),
        {"aid": str(analysis.id)},
    )
    db.commit()

    return AnalyzeResponse(task_id=task.id)


@router.get("/{factor_id}/analysis", response_model=list[AnalysisOut])
def list_analyses(
    factor_id: str,
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(FactorAnalysis).filter(FactorAnalysis.factor_id == factor_id)
    if status:
        q = q.filter(FactorAnalysis.status == status)
    analyses = q.order_by(FactorAnalysis.created_at.desc()).limit(20).all()
    return [
        AnalysisOut(
            id=str(a.id), factor_id=str(a.factor_id),
            start_date=a.start_date.isoformat(), end_date=a.end_date.isoformat(),
            group_count=a.group_count, forward_days=a.forward_days,
            ic_mean=a.ic_mean, ic_std=a.ic_std, icir=a.icir,
            ic_series=a.ic_series, layer_returns=a.layer_returns,
            layer_cumulative=a.layer_cumulative, monotonicity=a.monotonicity,
            status=a.status, error_message=a.error_message,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in analyses
    ]


@router.get("/{factor_id}/analysis/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    factor_id: str,
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(FactorAnalysis).filter(
        FactorAnalysis.id == analysis_id, FactorAnalysis.factor_id == factor_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisOut(
        id=str(a.id), factor_id=str(a.factor_id),
        start_date=a.start_date.isoformat(), end_date=a.end_date.isoformat(),
        group_count=a.group_count, forward_days=a.forward_days,
        ic_mean=a.ic_mean, ic_std=a.ic_std, icir=a.icir,
        ic_series=a.ic_series, layer_returns=a.layer_returns,
        layer_cumulative=a.layer_cumulative, monotonicity=a.monotonicity,
        status=a.status, error_message=a.error_message,
        created_at=a.created_at.isoformat() if a.created_at else None,
    )


@router.get("/{factor_id}/values", response_model=list[FactorValueOut])
def get_factor_values(
    factor_id: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    stock_code: str | None = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(FactorValue).filter(
        FactorValue.factor_id == factor_id,
        FactorValue.trade_date >= date.fromisoformat(start_date),
        FactorValue.trade_date <= date.fromisoformat(end_date),
    )
    if stock_code:
        q = q.filter(FactorValue.stock_code == stock_code)
    values = q.order_by(FactorValue.trade_date.desc(), FactorValue.stock_code).offset(offset).limit(limit).all()
    return [
        FactorValueOut(
            stock_code=v.stock_code,
            trade_date=v.trade_date.isoformat(),
            value=v.value,
            rank_pct=v.rank_pct,
        )
        for v in values
    ]
