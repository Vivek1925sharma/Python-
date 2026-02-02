from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, DefaultDict, List, Optional
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, Field, condecimal, constr

app = FastAPI(title="GenAI Payments", version="1.0.0")


class PaymentRequest(BaseModel):
    amount: condecimal(gt=0) = Field(..., description="Transaction amount")
    currency: constr(min_length=3, max_length=3) = Field("USD")
    customer_id: str = Field(..., min_length=3)
    merchant_id: str = Field(..., min_length=3)
    ip_country: str = Field(..., min_length=2, max_length=2)
    billing_country: str = Field(..., min_length=2, max_length=2)
    device_id: str = Field(..., min_length=6)
    card_bin: constr(min_length=6, max_length=8)
    timestamp: Optional[datetime] = None


class FraudScore(BaseModel):
    score: float
    decision: str
    reasons: List[str]
    ai_summary: str


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    fraud: FraudScore


class InsightResponse(BaseModel):
    customer_id: str
    recent_transactions: int
    ai_summary: str


RISKY_BINS = {"414720", "400551", "546891"}

_recent_activity: DefaultDict[str, Deque[datetime]] = defaultdict(lambda: deque(maxlen=20))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _record_activity(customer_id: str, when: datetime) -> None:
    _recent_activity[customer_id].append(when)


def _recent_count(customer_id: str, since: datetime) -> int:
    return sum(1 for ts in _recent_activity[customer_id] if ts >= since)


def score_fraud(request: PaymentRequest) -> FraudScore:
    reasons: List[str] = []
    score = 0.2

    amount = float(request.amount)
    if amount > 2000:
        score += 0.5
        reasons.append("High-ticket amount exceeds $2k.")
    elif amount > 500:
        score += 0.25
        reasons.append("Amount is above typical mid-tier threshold.")

    if request.ip_country.upper() != request.billing_country.upper():
        score += 0.2
        reasons.append("IP country differs from billing country.")

    if request.card_bin in RISKY_BINS:
        score += 0.2
        reasons.append("Card BIN appears on a watch list.")

    now = request.timestamp or _utc_now()
    _record_activity(request.customer_id, now)
    burst_count = _recent_count(request.customer_id, now - timedelta(minutes=5))
    if burst_count >= 5:
        score += 0.25
        reasons.append("High velocity: 5+ transactions in 5 minutes.")

    score = min(score, 1.0)
    decision = "approve" if score < 0.6 else "review" if score < 0.8 else "block"

    ai_summary = (
        f"AI risk summary: score={score:.2f} ({decision}). "
        f"Signals: {', '.join(reasons) if reasons else 'No elevated signals detected.'}"
    )

    return FraudScore(score=score, decision=decision, reasons=reasons, ai_summary=ai_summary)


def build_insight(customer_id: str) -> InsightResponse:
    now = _utc_now()
    count_24h = _recent_count(customer_id, now - timedelta(hours=24))
    ai_summary = (
        f"AI insight: Customer {customer_id} has {count_24h} transactions in the last 24 hours. "
        "Recommend monitoring if velocity exceeds historical baseline."
    )
    return InsightResponse(customer_id=customer_id, recent_transactions=count_24h, ai_summary=ai_summary)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/pay", response_model=PaymentResponse)
async def pay(request: PaymentRequest) -> PaymentResponse:
    fraud = score_fraud(request)
    status = "captured" if fraud.decision == "approve" else "pending_review" if fraud.decision == "review" else "blocked"
    return PaymentResponse(payment_id=str(uuid4()), status=status, fraud=fraud)


@app.get("/ai-insights/{customer_id}", response_model=InsightResponse)
async def insights(customer_id: str) -> InsightResponse:
    return build_insight(customer_id)
