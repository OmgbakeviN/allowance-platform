from decimal import Decimal
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from wallet.models import WalletTransaction, WalletBucket
from wallet.services import get_or_create_wallet_for_student, spent_today
from expenses.services import summary_for_student
from relationships.models import ParentStudentLink


def _d(v):
    return str(v or Decimal("0"))


def month_start(d):
    return d.replace(day=1)


def last_7_days_start(d):
    return d - timedelta(days=6)


def student_dashboard(student, date_from=None, date_to=None):
    today = timezone.localdate()
    ms = month_start(today)

    wallet = get_or_create_wallet_for_student(student)
    buckets = {b.bucket_type: b.balance for b in wallet.buckets.all()}

    daily_balance = buckets.get(WalletBucket.Type.DAILY, Decimal("0"))
    savings_balance = buckets.get(WalletBucket.Type.SAVINGS, Decimal("0"))
    bills_balance = buckets.get(WalletBucket.Type.BILLS, Decimal("0"))

    spent_today_amount = spent_today(wallet, WalletBucket.Type.DAILY)
    daily_limit = wallet.daily_limit or Decimal("0")
    daily_remaining_today = (daily_limit - spent_today_amount) if daily_limit > 0 else None

    total_month_expenses = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            txn_type=WalletTransaction.TxnType.EXPENSE,
            direction=WalletTransaction.Direction.DEBIT,
            created_at__date__gte=ms,
            created_at__date__lte=today,
        )
        .aggregate(s=Sum("amount"))
        .get("s")
        or Decimal("0")
    )

    days_left = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - today
    days_left_in_month = days_left.days

    recommended_per_day = (daily_balance / Decimal(days_left_in_month)) if days_left_in_month > 0 else daily_balance

    d7 = last_7_days_start(today)
    total_7d = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            txn_type=WalletTransaction.TxnType.EXPENSE,
            direction=WalletTransaction.Direction.DEBIT,
            created_at__date__gte=d7,
            created_at__date__lte=today,
        )
        .aggregate(s=Sum("amount"))
        .get("s")
        or Decimal("0")
    )
    avg_daily_7d = (total_7d / Decimal(7)) if total_7d > 0 else Decimal("0")
    depletion_days = (daily_balance / avg_daily_7d) if avg_daily_7d > 0 else None

    expense_summary = summary_for_student(student, date_from=date_from, date_to=date_to)

    return {
        "wallet": {
            "currency": wallet.currency,
            "daily_limit": _d(daily_limit),
            "buckets": {
                "DAILY": _d(daily_balance),
                "SAVINGS": _d(savings_balance),
                "BILLS": _d(bills_balance),
            },
        },
        "spending": {
            "spent_today": _d(spent_today_amount),
            "daily_remaining_today": _d(daily_remaining_today) if daily_remaining_today is not None else None,
            "total_month_expenses": _d(total_month_expenses),
        },
        "projection": {
            "days_left_in_month": days_left_in_month,
            "recommended_daily_spend": _d(recommended_per_day),
            "avg_daily_spend_7d": _d(avg_daily_7d),
            "estimated_days_until_daily_empty": _d(depletion_days) if depletion_days is not None else None,
        },
        "top_categories": expense_summary["top_categories"],
        "alerts": expense_summary["alerts"],
    }


def parent_student_dashboard(parent, student, date_from=None, date_to=None):
    today = timezone.localdate()
    ms = month_start(today)

    wallet = get_or_create_wallet_for_student(student)

    sent_this_month = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            actor=parent,
            txn_type=WalletTransaction.TxnType.DEPOSIT,
            direction=WalletTransaction.Direction.CREDIT,
            created_at__date__gte=ms,
            created_at__date__lte=today,
        )
        .aggregate(s=Sum("amount"))
        .get("s")
        or Decimal("0")
    )

    repartition = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            actor=parent,
            txn_type=WalletTransaction.TxnType.DEPOSIT,
            direction=WalletTransaction.Direction.CREDIT,
            created_at__date__gte=ms,
            created_at__date__lte=today,
        )
        .values("bucket_type")
        .annotate(total=Sum("amount"))
        .order_by()
    )

    expense_summary = summary_for_student(student, date_from=date_from, date_to=date_to)
    stu_dash = student_dashboard(student, date_from=date_from, date_to=date_to)

    return {
        "student": {
            "id": student.id,
            "username": student.username,
            "email": student.email,
        },
        "sent_this_month": _d(sent_this_month),
        "repartition_this_month": [
            {"bucket_type": r["bucket_type"], "total": _d(r["total"])} for r in repartition
        ],
        "wallet": stu_dash["wallet"],
        "spending": stu_dash["spending"],
        "top_categories": expense_summary["top_categories"],
        "alerts": expense_summary["alerts"],
    }


def parent_overview(parent, date_from=None, date_to=None):
    today = timezone.localdate()
    ms = month_start(today)

    links = ParentStudentLink.objects.filter(
        parent=parent, status=ParentStudentLink.Status.ACTIVE
    ).select_related("student")

    students = [l.student for l in links]

    total_sent = Decimal("0")
    per_student = []

    for student in students:
        dash = parent_student_dashboard(parent, student, date_from=date_from, date_to=date_to)
        total_sent += Decimal(dash["sent_this_month"])
        per_student.append(dash)

    return {
        "parent": {"id": parent.id, "username": parent.username, "email": parent.email},
        "total_sent_this_month": _d(total_sent),
        "students": per_student,
        "period": {"month_start": str(ms), "today": str(today)},
    }
