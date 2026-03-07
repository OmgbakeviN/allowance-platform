from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import transaction
from .models import ParentAccount, ParentAccountTransaction

Q = Decimal("0.01")

def _q(v):
    return (v or Decimal("0")).quantize(Q, rounding=ROUND_HALF_UP)

def get_or_create_parent_account(parent):
    acc, _ = ParentAccount.objects.get_or_create(parent=parent)
    return acc

def fee_percent():
    return getattr(settings, "PLATFORM_FEE_PERCENT", Decimal("0"))

@transaction.atomic
def topup(parent, amount, provider=None, external_ref=None, description=""):
    amount = _q(Decimal(amount))
    acc = ParentAccount.objects.select_for_update().get_or_create(parent=parent)[0]

    pct = fee_percent()
    fee = _q(amount * pct / Decimal("100"))
    net = _q(amount - fee)

    acc.balance = _q(acc.balance + net)
    acc.save(update_fields=["balance", "updated_at"])

    txn = ParentAccountTransaction.objects.create(
        account=acc,
        direction=ParentAccountTransaction.Direction.CREDIT,
        txn_type=ParentAccountTransaction.TxnType.TOPUP,
        gross_amount=amount,
        fee_amount=fee,
        net_amount=net,
        provider=provider,
        external_ref=external_ref,
        description=description,
        metadata={"fee_percent": str(pct)},
    )

    return acc, txn

@transaction.atomic
def transfer_out(parent, amount, external_ref=None, description="", metadata=None):
    if metadata is None:
        metadata = {}
    amount = _q(Decimal(amount))
    acc = ParentAccount.objects.select_for_update().get_or_create(parent=parent)[0]

    if _q(acc.balance) < amount:
        raise ValueError("INSUFFICIENT_PARENT_BALANCE")

    acc.balance = _q(acc.balance - amount)
    acc.save(update_fields=["balance", "updated_at"])

    txn = ParentAccountTransaction.objects.create(
        account=acc,
        direction=ParentAccountTransaction.Direction.DEBIT,
        txn_type=ParentAccountTransaction.TxnType.TRANSFER_OUT,
        gross_amount=amount,
        fee_amount=Decimal("0"),
        net_amount=amount,
        external_ref=external_ref,
        description=description,
        metadata=metadata,
    )

    return acc, txn