from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from wallet.services import get_or_create_wallet_for_student, debit, spent_today
from wallet.models import WalletBucket, WalletTransaction
from .models import ExpenseCategory, Expense


DEFAULT_CATEGORIES = [
    ("Food", "food"),
    ("Transport", "transport"),
    ("School", "school"),
    ("Health", "health"),
    ("Bills", "bills"),
    ("Entertainment", "entertainment"),
    ("Other", "other"),
]


def ensure_default_categories():
    for name, slug in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.get_or_create(
            owner=None,
            slug=slug,
            defaults={"name": name, "is_default": True},
        )


def categories_for_student(student):
    ensure_default_categories()
    return ExpenseCategory.objects.filter(owner__isnull=True).union(
        ExpenseCategory.objects.filter(owner=student)
    )


def get_category_for_student(student, category_id=None, category_slug=None):
    ensure_default_categories()

    if category_id:
        cat = ExpenseCategory.objects.get(id=category_id)
        if cat.owner is None or cat.owner_id == student.id:
            return cat
        raise ExpenseCategory.DoesNotExist()

    if category_slug:
        slug = slugify(category_slug)
        cat = ExpenseCategory.objects.filter(owner=student, slug=slug).first()
        if cat:
            return cat
        cat = ExpenseCategory.objects.filter(owner__isnull=True, slug=slug).first()
        if cat:
            return cat
        raise ExpenseCategory.DoesNotExist()

    return ExpenseCategory.objects.get(owner__isnull=True, slug="other")


def week_start(d: date):
    return d - timedelta(days=d.weekday())


def month_start(d: date):
    return d.replace(day=1)


def build_alerts(wallet):
    alerts = []
    limit = wallet.daily_limit or Decimal("0")
    if limit > 0:
        today_spent = spent_today(wallet, WalletBucket.Type.DAILY)
        if today_spent >= limit:
            alerts.append({"type": "DAILY_LIMIT_REACHED", "message": "Daily limit reached."})
        elif today_spent >= (limit * Decimal("0.8")):
            alerts.append({"type": "DAILY_LIMIT_NEAR", "message": "Near daily limit (>= 80%)."})
    return alerts


def create_expense(
    student,
    amount: Decimal,
    bucket_type: str,
    category,
    note: str = "",
    receipt=None,
    occurred_at=None,
):
    wallet = get_or_create_wallet_for_student(student)

    if occurred_at is None:
        occurred_at = timezone.now()

    txn = debit(
        wallet=wallet,
        actor=student,
        bucket_type=bucket_type,
        amount=amount,
        txn_type=WalletTransaction.TxnType.EXPENSE,
        description=note or "",
        metadata={"category_slug": category.slug, "category_name": category.name},
    )

    exp = Expense.objects.create(
        transaction=txn,
        wallet=wallet,
        student=student,
        category=category,
        amount=amount,
        bucket_type=bucket_type,
        note=note or "",
        receipt=receipt,
        occurred_at=occurred_at,
    )

    return wallet, exp, txn


def summary_for_student(student, date_from=None, date_to=None):
    qs = Expense.objects.filter(student=student)

    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)

    today = timezone.localdate()
    ws = week_start(today)
    ms = month_start(today)

    total_today = Expense.objects.filter(student=student, occurred_at__date=today).aggregate(s=Sum("amount")).get("s") or Decimal("0")
    total_week = Expense.objects.filter(student=student, occurred_at__date__gte=ws, occurred_at__date__lte=today).aggregate(s=Sum("amount")).get("s") or Decimal("0")
    total_month = Expense.objects.filter(student=student, occurred_at__date__gte=ms, occurred_at__date__lte=today).aggregate(s=Sum("amount")).get("s") or Decimal("0")

    top = (
        qs.values("category__slug", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:5]
    )

    wallet = get_or_create_wallet_for_student(student)
    alerts = build_alerts(wallet)

    return {
        "total_today": str(total_today),
        "total_week": str(total_week),
        "total_month": str(total_month),
        "top_categories": list(top),
        "alerts": alerts,
    }
