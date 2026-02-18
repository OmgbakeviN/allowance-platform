from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from wallet.models import Wallet, WalletTransaction, WalletBucket


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=60)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="expense_categories",
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(owner__isnull=True),
                name="uniq_default_category_slug",
            ),
            models.UniqueConstraint(
                fields=["owner", "slug"],
                condition=Q(owner__isnull=False),
                name="uniq_owner_category_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "slug"]),
        ]

    def __str__(self):
        return f"{self.slug}"


class Expense(models.Model):
    transaction = models.OneToOneField(
        WalletTransaction,
        on_delete=models.CASCADE,
        related_name="expense",
    )
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="expenses")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    bucket_type = models.CharField(max_length=10, choices=WalletBucket.Type.choices, default=WalletBucket.Type.DAILY)

    note = models.CharField(max_length=255, blank=True, default="")
    receipt = models.FileField(upload_to="receipts/", null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "occurred_at"]),
            models.Index(fields=["wallet", "occurred_at"]),
            models.Index(fields=["category", "occurred_at"]),
        ]

    def __str__(self):
        return f"Expense({self.student_id} {self.amount})"
