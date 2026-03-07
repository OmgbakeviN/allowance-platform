from rest_framework import serializers
from .models import ParentAccount, ParentAccountTransaction

class ParentAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentAccount
        fields = ["currency", "balance", "updated_at", "created_at"]

class ParentAccountTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentAccountTransaction
        fields = [
            "id", "direction", "txn_type", "gross_amount", "fee_amount", "net_amount",
            "provider", "external_ref", "description", "metadata", "created_at"
        ]

class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    provider = serializers.ChoiceField(choices=ParentAccountTransaction.Provider.choices)
    external_ref = serializers.CharField(max_length=80, required=False, allow_blank=True)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        return v