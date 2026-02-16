from decimal import Decimal
from rest_framework import serializers
from .models import BudgetPlan, BillItem


class BillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillItem
        fields = ["id", "title", "amount", "due_day", "priority", "is_mandatory", "created_at"]

    def validate_due_day(self, v):
        if v is None:
            return v
        if v < 1 or v > 31:
            raise serializers.ValidationError("due_day must be between 1 and 31.")
        return v

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("amount must be > 0.")
        return v


class BudgetPlanCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetPlan
        fields = [
            "id",
            "name",
            "currency",
            "daily_limit",
            "savings_mode",
            "savings_amount",
            "savings_percent",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at"]

    def validate(self, attrs):
        savings_mode = attrs.get("savings_mode", getattr(self.instance, "savings_mode", BudgetPlan.SavingsMode.NONE))
        savings_amount = attrs.get("savings_amount", getattr(self.instance, "savings_amount", Decimal("0")))
        savings_percent = attrs.get("savings_percent", getattr(self.instance, "savings_percent", Decimal("0")))

        if savings_mode == BudgetPlan.SavingsMode.AMOUNT and savings_amount <= 0:
            raise serializers.ValidationError({"savings_amount": "Required and must be > 0 for AMOUNT mode."})

        if savings_mode == BudgetPlan.SavingsMode.PERCENT:
            if savings_percent <= 0 or savings_percent > 100:
                raise serializers.ValidationError({"savings_percent": "Must be > 0 and <= 100 for PERCENT mode."})

        if savings_mode == BudgetPlan.SavingsMode.NONE:
            attrs["savings_amount"] = Decimal("0")
            attrs["savings_percent"] = Decimal("0")

        return attrs


class BudgetPlanDetailSerializer(serializers.ModelSerializer):
    bills = BillItemSerializer(many=True)

    total_bills = serializers.SerializerMethodField()

    class Meta:
        model = BudgetPlan
        fields = [
            "id",
            "name",
            "currency",
            "daily_limit",
            "savings_mode",
            "savings_amount",
            "savings_percent",
            "status",
            "created_at",
            "updated_at",
            "bills",
            "total_bills",
        ]

    def get_total_bills(self, obj):
        return str(sum([b.amount for b in obj.bills.all()], Decimal("0")))
