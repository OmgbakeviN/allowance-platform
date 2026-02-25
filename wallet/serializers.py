from decimal import Decimal
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from accounts.permissions import IsParent, IsStudent
from relationships.models import ParentStudentLink
from .models import Wallet, WalletBucket, WalletTransaction
from .services import get_or_create_wallet_for_student, credit, debit, spent_today
from budgeting.allocation import compute_allocation
from budgeting.models import BudgetPlan

User = get_user_model()




class WalletBucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletBucket
        fields = ["bucket_type", "balance", "updated_at"]


class WalletSerializer(serializers.ModelSerializer):
    buckets = WalletBucketSerializer(many=True)

    class Meta:
        model = Wallet
        fields = ["id", "currency", "daily_limit", "created_at", "buckets"]


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "bucket_type",
            "direction",
            "txn_type",
            "amount",
            "description",
            "external_ref",
            "metadata",
            "created_at",
        ]


class WalletSettingsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["currency", "daily_limit"]


class DepositSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    external_ref = serializers.CharField(max_length=80, required=False, allow_blank=True)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        return v

    def validate(self, attrs):
        parent = self.context["request"].user
        student_id = attrs["student_id"]

        if not (parent.is_superuser or getattr(parent, "role", None) in {"ADMIN", "PARENT"}):
            raise serializers.ValidationError("Only parents/admin can deposit.")

        ok = (
            ParentStudentLink.objects.filter(
                parent=parent, student_id=student_id, status=ParentStudentLink.Status.ACTIVE
            ).exists()
            or parent.is_superuser
            or getattr(parent, "role", None) == "ADMIN"
        )

        if not ok:
            raise serializers.ValidationError("Parent not linked to this student.")

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        parent = self.context["request"].user
        student = User.objects.get(id=validated_data["student_id"])
        wallet = get_or_create_wallet_for_student(student)

        amount = validated_data["amount"]
        ext = (validated_data.get("external_ref") or "").strip() or None
        desc = validated_data.get("description", "")

        group_ref = ext or f"AUTO-{uuid4().hex[:10].upper()}"

        plan = (
            BudgetPlan.objects.prefetch_related("bills")
            .filter(student=student, status=BudgetPlan.Status.ACTIVE)
            .order_by("-created_at")
            .first()
        )

        txns = []

        if not plan:
            meta = {"allocation": "AUTO_FALLBACK", "group_ref": group_ref}
            txns.append(
                credit(
                    wallet,
                    parent,
                    WalletBucket.Type.DAILY,
                    amount,
                    WalletTransaction.TxnType.DEPOSIT,
                    desc,
                    external_ref=(f"{group_ref}-DAILY"[:80]),
                    metadata=meta,
                )
            )
            return wallet, txns

        alloc = compute_allocation(plan, Decimal(amount))

        wallet.currency = alloc["currency"] or wallet.currency
        wallet.daily_limit = Decimal(alloc["daily_limit"])
        wallet.save(update_fields=["currency", "daily_limit"])

        meta_base = {
            "allocation": "AUTO_PLAN",
            "group_ref": group_ref,
            "plan_id": alloc["plan_id"],
            "deposit_amount": alloc["deposit_amount"],
            "savings_target": alloc["savings_target"],
        }

        bills_amount = Decimal(alloc["bills_allocated"])
        savings_amount = Decimal(alloc["savings_allocated"])
        daily_amount = Decimal(alloc["daily_allocated"])

        if bills_amount > 0:
            txns.append(
                credit(
                    wallet,
                    parent,
                    WalletBucket.Type.BILLS,
                    bills_amount,
                    WalletTransaction.TxnType.DEPOSIT,
                    desc,
                    external_ref=(f"{group_ref}-BILLS"[:80]),
                    metadata={**meta_base, "bills_breakdown": alloc["bills_breakdown"]},
                )
            )

        if savings_amount > 0:
            txns.append(
                credit(
                    wallet,
                    parent,
                    WalletBucket.Type.SAVINGS,
                    savings_amount,
                    WalletTransaction.TxnType.DEPOSIT,
                    desc,
                    external_ref=(f"{group_ref}-SAVINGS"[:80]),
                    metadata=meta_base,
                )
            )

        if daily_amount > 0:
            txns.append(
                credit(
                    wallet,
                    parent,
                    WalletBucket.Type.DAILY,
                    daily_amount,
                    WalletTransaction.TxnType.DEPOSIT,
                    desc,
                    external_ref=(f"{group_ref}-DAILY"[:80]),
                    metadata=meta_base,
                )
            )

        return wallet, txns


class ExpenseSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    bucket_type = serializers.ChoiceField(choices=WalletBucket.Type.choices, default=WalletBucket.Type.DAILY)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        return v

    def validate(self, attrs):
        student = self.context["request"].user
        wallet = get_or_create_wallet_for_student(student)
        attrs["_wallet"] = wallet

        bucket_type = attrs["bucket_type"]
        if bucket_type == WalletBucket.Type.DAILY:
            limit = wallet.daily_limit or Decimal("0")
            if limit > 0:
                today_spent = spent_today(wallet, WalletBucket.Type.DAILY)
                if today_spent + attrs["amount"] > limit:
                    raise serializers.ValidationError({"amount": "Daily limit exceeded."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        student = self.context["request"].user
        wallet = validated_data["_wallet"]
        amount = validated_data["amount"]
        bucket_type = validated_data["bucket_type"]
        desc = validated_data.get("description", "")
        txn = debit(wallet, student, bucket_type, amount, WalletTransaction.TxnType.EXPENSE, desc)
        return wallet, txn
