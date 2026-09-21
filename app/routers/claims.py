from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from app.db import get_session
from app.models import (
    Claim,
    ClaimCreate,
    ClaimRead,
    ClaimStatus,
    ClaimStatusUpdate,
    Policy,
    PolicyStatus,
    ProductCode,
)


router = APIRouter(prefix="/api/claims", tags=["claims"])


ALLOWED_TRANSITIONS = {
    ClaimStatus.FILED: {ClaimStatus.UNDER_REVIEW, ClaimStatus.REJECTED},
    ClaimStatus.UNDER_REVIEW: {ClaimStatus.APPROVED, ClaimStatus.REJECTED},
}


def approved_total(session: Session, policy_id: int) -> float:
    total = session.exec(
        select(func.sum(Claim.amount)).where(
            Claim.policy_id == policy_id,
            Claim.status == ClaimStatus.APPROVED,
        )
    ).one()

    return float(total or 0.0)


def remaining_cover(session: Session, policy: Policy) -> float:
    return policy.sum_insured - approved_total(session, policy.id)


def file_claim(payload: ClaimCreate, session: Session) -> Claim:
    # 1. Check that the policy exists.
    policy = session.get(Policy, payload.policy_id)

    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    # 2. Cancelled policies accept the claim but immediately reject it.
    if policy.status == PolicyStatus.CANCELLED:
        claim = Claim.model_validate(payload)
        claim.status = ClaimStatus.REJECTED
        claim.reason = "Policy is cancelled"

        session.add(claim)
        session.commit()
        session.refresh(claim)

        return claim

    # 3. Only active policies accept claims.
    if policy.status != PolicyStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Policy is {policy.status.value.lower()}; "
                "only Active policies accept claims"
            ),
        )

    # 4. Incident date must fall within the policy period.
    if not (
        policy.start_date
        <= payload.incident_date
        <= policy.end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Incident date must fall within the policy period "
                f"{policy.start_date} to {policy.end_date}"
            ),
        )

    # 5. Claim cannot exceed the remaining cover.
    remaining = remaining_cover(session, policy)

    if payload.amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Claim amount exceeds remaining cover of "
                f"{remaining:,.2f}"
            ),
        )

    # 6. Motor claims require vehicle registration.
    if (
        policy.product.code == ProductCode.MOTOR
        and not (payload.vehicle_registration or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Motor claims need a vehicle registration number",
        )

    claim = Claim.model_validate(payload)

    session.add(claim)
    session.commit()
    session.refresh(claim)

    return claim


@router.get("", response_model=list[ClaimRead])
def list_claims(
    policy_id: int | None = None,
    status: ClaimStatus | None = None,
    session: Session = Depends(get_session),
) -> list[ClaimRead]:
    statement = select(Claim).order_by(Claim.created_at.desc())

    if policy_id is not None:
        statement = statement.where(
            Claim.policy_id == policy_id
        )

    if status is not None:
        statement = statement.where(
            Claim.status == status
        )

    return list(session.exec(statement).all())


@router.post(
    "",
    response_model=ClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def create_claim(
    payload: ClaimCreate,
    session: Session = Depends(get_session),
) -> ClaimRead:
    return file_claim(payload, session)


@router.get("/{claim_id}", response_model=ClaimRead)
def get_claim(
    claim_id: int,
    session: Session = Depends(get_session),
) -> ClaimRead:
    claim = session.get(Claim, claim_id)

    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    return claim


@router.patch("/{claim_id}/status", response_model=ClaimRead)
def update_claim_status(
    claim_id: int,
    payload: ClaimStatusUpdate,
    session: Session = Depends(get_session),
) -> ClaimRead:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    allowed = ALLOWED_TRANSITIONS.get(claim.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition claim status from {claim.status.value} to {payload.status.value}",
        )

    if payload.status == ClaimStatus.APPROVED:
        policy = session.get(Policy, claim.policy_id)
        if policy:
            remaining = remaining_cover(session, policy)
            if claim.amount > remaining:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Claim amount exceeds remaining cover of {remaining:,.2f}",
                )

    claim.status = payload.status
    if payload.reason is not None:
        claim.reason = payload.reason

    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim