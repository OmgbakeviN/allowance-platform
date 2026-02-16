from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import Wallet, WalletBucket, WalletTransaction

User = get_user_model()


def get_or_create_wallet_for_student(student: User) -> Wallet:
    wallet, created = Wallet.objects.get_or_create(student=student)
    if created:
        WalletBucket.objects.get_or_create(wallet=wallet, bucket_type=WalletBucket.Type.BILLS)
        WalletBucket.objects.get_or_create(wallet=wallet, bucket_type=WalletBucket.Type.SAVINGS)
        WalletBucket.objects.get_or_create(wallet=wallet, bucket_type=WalletBucket.Type.DAILY)
    return wallet


def get_bucket_locked(wallet: Wallet, bucket_type: str) -> WalletBucket:
    bucket, _ = WalletBucket.objects.select_for_update().get_or_create(wallet=wallet, bucket_type=bucket_type)
    return bucket


def credit(wallet: Wallet, actor, bucket_type: str, amount: Decimal, txn_type: str, description: str = "", external_ref: str = None, metadata=None):
    if metadata is None:
        metadata = {}
    bucket = get_bucket_locked(wallet, bucket_type)
    bucket.balance = (bucket.balance or Decimal("0")) + amount
    bucket.save(update_fields=["balance", "updated_at"])
    return WalletTransaction.objects.create(
        wallet=wallet,
        actor=actor,
        bucket_type=bucket_type,
        direction=WalletTransaction.Direction.CREDIT,
        txn_type=txn_type,
        amount=amount,
        description=description,
        external_ref=external_ref,
        metadata=metadata,
    )


def debit(wallet: Wallet, actor, bucket_type: str, amount: Decimal, txn_type: str, description: str = "", metadata=None):
    if metadata is None:
        metadata = {}
    bucket = get_bucket_locked(wallet, bucket_type)
    if (bucket.balance or Decimal("0")) < amount:
        raise ValueError("Insufficient funds.")
    bucket.balance = (bucket.balance or Decimal("0")) - amount
    bucket.save(update_fields=["balance", "updated_at"])
    return WalletTransaction.objects.create(
        wallet=wallet,
        actor=actor,
        bucket_type=bucket_type,
        direction=WalletTransaction.Direction.DEBIT,
        txn_type=txn_type,
        amount=amount,
        description=description,
        metadata=metadata,
    )


def spent_today(wallet: Wallet, bucket_type: str) -> Decimal:
    from django.db.models import Sum
    today = timezone.localdate()
    total = (
        WalletTransaction.objects.filter(
            wallet=wallet,
            bucket_type=bucket_type,
            direction=WalletTransaction.Direction.DEBIT,
            txn_type=WalletTransaction.TxnType.EXPENSE,
            created_at__date=today,
        )
        .aggregate(s=Sum("amount"))
        .get("s")
    )
    return total or Decimal("0")
