from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from accounts.permissions import IsParent, IsStudent
from relationships.models import ParentStudentLink
from .models import Wallet, WalletBucket, WalletTransaction
from .services import get_or_create_wallet_for_student, credit, debit, spent_today

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

    bills_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    savings_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    daily_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        return v

    def validate(self, attrs):
        parent = self.context["request"].user
        student_id = attrs["student_id"]

        if not (parent.is_superuser or getattr(parent, "role", None) in {"ADMIN", "PARENT"}):
            raise serializers.ValidationError("Only parents/admin can deposit.")

        ok = ParentStudentLink.objects.filter(
            parent=parent, student_id=student_id, status=ParentStudentLink.Status.ACTIVE
        ).exists() or parent.is_superuser or getattr(parent, "role", None) == "ADMIN"

        if not ok:
            raise serializers.ValidationError("Parent not linked to this student.")

        split_fields = ["bills_amount", "savings_amount", "daily_amount"]
        provided = [f for f in split_fields if f in attrs]
        if provided:
            total = sum([attrs.get("bills_amount", Decimal("0")), attrs.get("savings_amount", Decimal("0")), attrs.get("daily_amount", Decimal("0"))])
            if total != attrs["amount"]:
                raise serializers.ValidationError("Split amounts must sum exactly to amount.")
            for f in provided:
                if attrs.get(f, Decimal("0")) < 0:
                    raise serializers.ValidationError("Split amounts must be >= 0.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        parent = self.context["request"].user
        student = User.objects.get(id=validated_data["student_id"])
        wallet = get_or_create_wallet_for_student(student)

        amount = validated_data["amount"]
        ext = validated_data.get("external_ref") or None
        desc = validated_data.get("description", "")

        bills = validated_data.get("bills_amount")
        savings = validated_data.get("savings_amount")
        daily = validated_data.get("daily_amount")

        if bills is None and savings is None and daily is None:
            daily = amount
            bills = Decimal("0")
            savings = Decimal("0")

        txns = []
        if bills and bills > 0:
            txns.append(
                credit(wallet, parent, WalletBucket.Type.BILLS, bills, WalletTransaction.TxnType.DEPOSIT, desc, external_ref=(ext + "-B") if ext else None, metadata={"student_id": student.id})
            )
        if savings and savings > 0:
            txns.append(
                credit(wallet, parent, WalletBucket.Type.SAVINGS, savings, WalletTransaction.TxnType.DEPOSIT, desc, external_ref=(ext + "-S") if ext else None, metadata={"student_id": student.id})
            )
        if daily and daily > 0:
            txns.append(
                credit(wallet, parent, WalletBucket.Type.DAILY, daily, WalletTransaction.TxnType.DEPOSIT, desc, external_ref=(ext + "-D") if ext else None, metadata={"student_id": student.id})
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
