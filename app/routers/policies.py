"""Policies API.   *** DAY 2, LAB 2: YOUR CODE HERE ***

POST  /api/policies              -> issue a policy from a quote
PATCH /api/policies/{id}/status  -> Active / Lapsed / Cancelled

Rules for issuing
    404 if the quote does not exist
    409 if the quote already has a policy
    422 if the product is MOTOR and no vehicle_registration was given
    policy_number = PD-<PRODUCT CODE>-<start year>-<5-digit sequence>, e.g. PD-MOTOR-2026-00007
    end_date     = start_date + (365 x tenure_years) days - 1 day
    copy customer_id, product_id, sum_insured and premium from the quote

Rules for status
    404 if the policy does not exist
    409 if the policy is already Cancelled (cancelled is final)
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db import get_session
from app.models import (
    Policy,
    PolicyCreate,
    PolicyRead,
    PolicyStatus,
    PolicyStatusUpdate,
    ProductCode,
    Quote,
)

router = APIRouter(prefix="/api/policies", tags=["policies"])


def next_policy_number(session: Session, product_code: ProductCode, start: date) -> str:
    """PD-<PRODUCT>-<YEAR>-<sequence>, e.g. PD-MOTOR-2026-00007. (Given.)"""
    count = session.exec(select(Policy.id)).all()
    return f"PD-{product_code.value}-{start.year}-{len(count) + 1:05d}"


def issue_policy(payload: PolicyCreate, session: Session) -> Policy:
    """Shared by the API and the HTML form. Raise HTTPException with the right status code on failure."""
    quote = session.get(Quote, payload.quote_id)
    if not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")
    if quote.policy is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote has already been converted to a policy")
    if quote.product.code == ProductCode.MOTOR and not (payload.vehicle_registration or "").strip():
        raise HTTPException(422, "Motor policies need a vehicle registration number")

    end_date = payload.start_date + timedelta(days=365 * quote.tenure_years) - timedelta(days=1)
    policy = Policy(
        quote_id=quote.id,
        policy_number=next_policy_number(session, quote.product.code, payload.start_date),
        customer_id=quote.customer_id,
        product_id=quote.product_id,
        sum_insured=quote.sum_insured,
        premium=quote.premium,
        start_date=payload.start_date,
        end_date=end_date,
        vehicle_registration=(payload.vehicle_registration or "").strip().upper() or None,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


@router.get("", response_model=list[PolicyRead])
def list_policies(status_filter: PolicyStatus | None = None, session: Session = Depends(get_session)):
    stmt = select(Policy).order_by(Policy.created_at.desc())
    if status_filter:
        stmt = stmt.where(Policy.status == status_filter)
    return session.exec(stmt).all()


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create_policy(payload: PolicyCreate, session: Session = Depends(get_session)):
    return issue_policy(payload, session)


@router.get("/{policy_id}", response_model=PolicyRead)
def get_policy(policy_id: int, session: Session = Depends(get_session)):
    policy = session.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    return policy


@router.patch("/{policy_id}/status", response_model=PolicyRead)
def update_policy_status(policy_id: int, payload: PolicyStatusUpdate, session: Session = Depends(get_session)):
    policy = session.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    if policy.status == PolicyStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "A cancelled policy cannot be changed")
    policy.status = payload.status
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy
