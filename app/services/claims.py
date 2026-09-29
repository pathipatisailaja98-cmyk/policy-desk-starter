"""Claim validation rules.   *** LAB 3: YOUR CODE HERE ***

A claim is accepted for filing only if:
    1. The policy is Active.
         Cancelled -> raise ClaimValidationError(..., auto_reject=True)
         Lapsed    -> raise ClaimValidationError(...)
    2. The incident date falls within the policy period
       (start and end dates inclusive)
    3. amount <= remaining cover
       (sum insured - claims already APPROVED on this policy)
    4. Motor claims include a vehicle registration number

Status workflow:
    Filed -> Under Review -> Approved / Rejected.
    Approved and Rejected are final.
"""

from datetime import date

from sqlmodel import Session, select

from app.models import Claim, ClaimStatus, Policy, PolicyStatus, ProductCode


class ClaimValidationError(ValueError):
    """Claim breaks a business rule.

    auto_reject=True means the claim should be stored as Rejected.
    """

    def __init__(self, message: str, auto_reject: bool = False):
        super().__init__(message)
        self.auto_reject = auto_reject


def approved_total(session: Session, policy_id: int) -> float:
    """Sum of APPROVED claim amounts on a policy."""
    rows = session.exec(
        select(Claim.amount).where(
            Claim.policy_id == policy_id,
            Claim.status == ClaimStatus.APPROVED,
        )
    ).all()

    return float(sum(rows))


def remaining_cover(session: Session, policy: Policy) -> float:
    """Sum insured minus approved claims."""
    return policy.sum_insured - approved_total(
        session,
        policy.id,
    )


def validate_claim(
    session: Session,
    policy: Policy,
    *,
    amount: float,
    incident_date: date,
    vehicle_registration: str | None,
) -> None:
    """Validate a claim according to Lab 3 rules."""

    # ------------------------------------------------------------------ #
    # Rule 1: Policy must be Active
    # ------------------------------------------------------------------ #

    if policy.status == PolicyStatus.CANCELLED:
        raise ClaimValidationError(
            "Cannot file a claim on a cancelled policy",
            auto_reject=True,
        )

    if policy.status == PolicyStatus.LAPSED:
        raise ClaimValidationError(
            "Cannot file a claim on a lapsed policy"
        )

    # ------------------------------------------------------------------ #
    # Rule 2: Incident date must be inside policy period
    # ------------------------------------------------------------------ #

    if (
        incident_date < policy.start_date
        or incident_date > policy.end_date
    ):
        raise ClaimValidationError(
            "Incident date must fall within the policy period"
        )

    # ------------------------------------------------------------------ #
    # Rule 3: Claim amount must not exceed remaining cover
    # ------------------------------------------------------------------ #

    remaining = remaining_cover(session, policy)

    if amount > remaining:
        raise ClaimValidationError(
            f"Claim amount exceeds remaining cover of {remaining:.2f}"
        )

    # ------------------------------------------------------------------ #
    # Rule 4: Motor claims need vehicle registration
    # ------------------------------------------------------------------ #

    if policy.product.code == ProductCode.MOTOR:
        if not (vehicle_registration or "").strip():
            raise ClaimValidationError(
                "Motor claims need a vehicle registration number"
            )


# --------------------------------------------------------------------------- #
# Claim status workflow
# --------------------------------------------------------------------------- #

ALLOWED_TRANSITIONS: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.FILED: {
        ClaimStatus.UNDER_REVIEW,
        ClaimStatus.REJECTED,
    },

    ClaimStatus.UNDER_REVIEW: {
        ClaimStatus.APPROVED,
        ClaimStatus.REJECTED,
    },

    ClaimStatus.APPROVED: set(),

    ClaimStatus.REJECTED: set(),
}


def can_transition(
    current: ClaimStatus,
    new: ClaimStatus,
) -> bool:
    return new in ALLOWED_TRANSITIONS[current]