"""Claims API. *** LAB 3: YOUR CODE HERE ***

POST /api/claims -> file a claim (201)

PATCH /api/claims/{id}/status -> move a claim through the workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status

from sqlmodel import Session, select

from app.db import get_session

from app.models import (
    Claim,
    ClaimCreate,
    ClaimRead,
    ClaimStatus,
    ClaimStatusUpdate,
    Policy,
)

from app.services import claims as claim_rules


router = APIRouter(
    prefix="/api/claims",
    tags=["claims"],
)


# ---------------------------------------------------------------------------
# File a claim
# ---------------------------------------------------------------------------

def file_claim(
    payload: ClaimCreate,
    session: Session,
) -> Claim:
    """Shared by the API and the HTML form."""

    # 1. Find the policy
    policy = session.get(Policy, payload.policy_id)

    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    # 2. Validate the claim using the Lab 3 business rules
    try:
        claim_rules.validate_claim(
            session,
            policy,
            amount=payload.amount,
            incident_date=payload.incident_date,
            vehicle_registration=payload.vehicle_registration,
        )

    except claim_rules.ClaimValidationError as exc:

        # Cancelled policy:
        # save the claim as Rejected
        if exc.auto_reject:
            claim = Claim.model_validate(payload)

            claim.status = ClaimStatus.REJECTED
            claim.reason = str(exc)

            session.add(claim)
            session.commit()
            session.refresh(claim)

            return claim

        # Other validation failures -> 422
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 3. Valid claim -> Filed
    claim = Claim.model_validate(payload)

    claim.status = ClaimStatus.FILED
    claim.reason = None

    session.add(claim)
    session.commit()
    session.refresh(claim)

    return claim


# ---------------------------------------------------------------------------
# List claims
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[ClaimRead],
)
def list_claims(
    policy_id: int | None = None,
    session: Session = Depends(get_session),
):
    stmt = select(Claim).order_by(Claim.created_at.desc())

    if policy_id:
        stmt = stmt.where(
            Claim.policy_id == policy_id
        )

    return session.exec(stmt).all()


# ---------------------------------------------------------------------------
# Create claim
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def create_claim(
    payload: ClaimCreate,
    session: Session = Depends(get_session),
):
    return file_claim(payload, session)


# ---------------------------------------------------------------------------
# Get one claim
# ---------------------------------------------------------------------------

@router.get(
    "/{claim_id}",
    response_model=ClaimRead,
)
def get_claim(
    claim_id: int,
    session: Session = Depends(get_session),
):
    claim = session.get(Claim, claim_id)

    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    return claim


# ---------------------------------------------------------------------------
# Update claim status
# ---------------------------------------------------------------------------

@router.patch(
    "/{claim_id}/status",
    response_model=ClaimRead,
)
def update_claim_status(
    claim_id: int,
    payload: ClaimStatusUpdate,
    session: Session = Depends(get_session),
):
    # 1. Find claim
    claim = session.get(Claim, claim_id)

    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    # 2. Check whether the status transition is allowed
    if not claim_rules.can_transition(
        claim.status,
        payload.status,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot change claim status from "
                f"{claim.status.value} to "
                f"{payload.status.value}"
            ),
        )

    # 3. When approving, check remaining cover
    if payload.status == ClaimStatus.APPROVED:

        remaining = claim_rules.remaining_cover(
            session,
            claim.policy,
        )

        if claim.amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Claim amount exceeds remaining cover "
                    f"of {remaining:.2f}"
                ),
            )

    # 4. Update status
    claim.status = payload.status

    # 5. Store the reason
    claim.reason = (
        payload.reason.strip()
        if payload.reason and payload.reason.strip()
        else None
    )

    session.add(claim)
    session.commit()
    session.refresh(claim)

    return claim