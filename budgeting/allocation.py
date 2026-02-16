from decimal import Decimal, ROUND_HALF_UP
from .models import BudgetPlan

Q = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return (v or Decimal("0")).quantize(Q, rounding=ROUND_HALF_UP)


def compute_allocation(plan: BudgetPlan, deposit_amount: Decimal) -> dict:
    amount = _q(deposit_amount)
    remaining = amount

    bills_breakdown = []
    bills_allocated = Decimal("0")

    bills = plan.bills.all().order_by("priority", "created_at")
    for bill in bills:
        if remaining <= 0:
            break
        need = _q(bill.amount)
        alloc = need if remaining >= need else remaining
        alloc = _q(alloc)
        if alloc > 0:
            bills_breakdown.append(
                {"bill_id": bill.id, "title": bill.title, "need": str(need), "allocated": str(alloc)}
            )
            bills_allocated += alloc
            remaining -= alloc
            remaining = _q(remaining)

    savings_target = Decimal("0")
    if plan.savings_mode == BudgetPlan.SavingsMode.AMOUNT:
        savings_target = _q(plan.savings_amount)
    elif plan.savings_mode == BudgetPlan.SavingsMode.PERCENT:
        savings_target = _q(amount * _q(plan.savings_percent) / Decimal("100"))

    savings_allocated = Decimal("0")
    if remaining > 0 and savings_target > 0:
        savings_allocated = savings_target if remaining >= savings_target else remaining
        savings_allocated = _q(savings_allocated)
        remaining -= savings_allocated
        remaining = _q(remaining)

    daily_allocated = _q(remaining)

    return {
        "plan_id": plan.id,
        "deposit_amount": str(amount),
        "bills_allocated": str(_q(bills_allocated)),
        "bills_breakdown": bills_breakdown,
        "savings_target": str(_q(savings_target)),
        "savings_allocated": str(_q(savings_allocated)),
        "daily_allocated": str(_q(daily_allocated)),
        "currency": plan.currency,
        "daily_limit": str(_q(plan.daily_limit)),
    }
