from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Wallet(models.Model):
    student = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    currency = models.CharField(max_length=8, default="XAF")
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wallet({self.student_id})"


class WalletBucket(models.Model):
    class Type(models.TextChoices):
        BILLS = "BILLS", "Bills"
        SAVINGS = "SAVINGS", "Savings"
        DAILY = "DAILY", "Daily"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="buckets")
    bucket_type = models.CharField(max_length=10, choices=Type.choices)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["wallet", "bucket_type"], name="uniq_wallet_bucket"),
        ]

    def __str__(self):
        return f"{self.wallet_id}:{self.bucket_type}"


class WalletTransaction(models.Model):
    class Direction(models.TextChoices):
        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"

    class TxnType(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        ALLOCATION = "ALLOCATION", "Allocation"
        EXPENSE = "EXPENSE", "Expense"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_actions"
    )
    bucket_type = models.CharField(max_length=10, choices=WalletBucket.Type.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    txn_type = models.CharField(max_length=20, choices=TxnType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, default="")
    external_ref = models.CharField(max_length=80, null=True, blank=True, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["wallet", "bucket_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.wallet_id} {self.txn_type} {self.direction} {self.amount}"
