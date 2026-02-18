from decimal import Decimal
from django.utils.dateparse import parse_date
from rest_framework import serializers

from wallet.models import WalletBucket
from wallet.services import get_or_create_wallet_for_student, spent_today
from .models import ExpenseCategory, Expense
from .services import get_category_for_student, categories_for_student, create_expense


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "slug", "is_default", "created_at"]


class CategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "slug"]

    def validate(self, attrs):
        name = attrs.get("name", "").strip()
        slug = (attrs.get("slug") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Required."})
        if not slug:
            raise serializers.ValidationError({"slug": "Required."})
        return attrs

    def create(self, validated_data):
        student = self.context["request"].user
        return ExpenseCategory.objects.create(owner=student, is_default=False, **validated_data)


class ExpenseListSerializer(serializers.ModelSerializer):
    category = ExpenseCategorySerializer()

    class Meta:
        model = Expense
        fields = [
            "id",
            "amount",
            "bucket_type",
            "note",
            "occurred_at",
            "created_at",
            "category",
            "receipt",
            "transaction_id",
        ]


class ExpenseCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    bucket_type = serializers.ChoiceField(choices=WalletBucket.Type.choices, default=WalletBucket.Type.DAILY)

    category_id = serializers.IntegerField(required=False)
    category_slug = serializers.CharField(required=False, allow_blank=True)

    note = serializers.CharField(max_length=255, required=False, allow_blank=True)
    occurred_at = serializers.DateTimeField(required=False)
    receipt = serializers.FileField(required=False)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        return v

    def validate(self, attrs):
        student = self.context["request"].user
        wallet = get_or_create_wallet_for_student(student)

        bucket_type = attrs["bucket_type"]
        if bucket_type == WalletBucket.Type.DAILY:
            limit = wallet.daily_limit or Decimal("0")
            if limit > 0:
                today_spent = spent_today(wallet, WalletBucket.Type.DAILY)
                if today_spent + attrs["amount"] > limit:
                    raise serializers.ValidationError({"amount": "Daily limit exceeded."})

        try:
            category = get_category_for_student(
                student,
                category_id=attrs.get("category_id"),
                category_slug=attrs.get("category_slug"),
            )
        except Exception:
            raise serializers.ValidationError({"category": "Invalid category."})

        attrs["_category"] = category
        return attrs

    def create(self, validated_data):
        student = self.context["request"].user
        category = validated_data["_category"]
        wallet, exp, txn = create_expense(
            student=student,
            amount=validated_data["amount"],
            bucket_type=validated_data["bucket_type"],
            category=category,
            note=validated_data.get("note", ""),
            receipt=validated_data.get("receipt"),
            occurred_at=validated_data.get("occurred_at"),
        )
        return exp
