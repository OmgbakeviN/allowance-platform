from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL

class ParentAccount(models.Model):
    parent = models.OneToOneField(User, on_delete=models.CASCADE, related_name="parent_account")
    currency = models.CharField(max_length=8, default="XAF")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ParentAccountTransaction(models.Model):
    class Direction(models.TextChoices):
        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"

    class TxnType(models.TextChoices):
        TOPUP = "TOPUP", "Topup"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"

    class Provider(models.TextChoices):
        MTN = "MTN", "MTN Money"
        ORANGE = "ORANGE", "Orange Money"

    account = models.ForeignKey(ParentAccount, on_delete=models.CASCADE, related_name="transactions")
    direction = models.CharField(max_length=10, choices=Direction.choices)
    txn_type = models.CharField(max_length=20, choices=TxnType.choices)

    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    provider = models.CharField(max_length=10, choices=Provider.choices, null=True, blank=True)
    external_ref = models.CharField(max_length=80, null=True, blank=True, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["account", "created_at"])]