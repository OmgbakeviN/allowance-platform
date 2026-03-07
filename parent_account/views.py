from rest_framework import generics, permissions, status
from rest_framework.response import Response
from accounts.permissions import IsParent
from .services import get_or_create_parent_account, topup
from .models import ParentAccountTransaction
from .serializers import ParentAccountSerializer, ParentAccountTransactionSerializer, TopUpSerializer

class ParentAccountMeAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = ParentAccountSerializer

    def get_object(self):
        return get_or_create_parent_account(self.request.user)

class ParentAccountTransactionsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = ParentAccountTransactionSerializer

    def get_queryset(self):
        acc = get_or_create_parent_account(self.request.user)
        return ParentAccountTransaction.objects.filter(account=acc).order_by("-created_at")

class ParentTopUpAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = TopUpSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        acc, txn = topup(
            parent=request.user,
            amount=s.validated_data["amount"],
            provider=s.validated_data["provider"],
            external_ref=(s.validated_data.get("external_ref") or "").strip() or None,
            description=s.validated_data.get("description", ""),
        )
        return Response(
            {
                "account": ParentAccountSerializer(acc).data,
                "transaction": ParentAccountTransactionSerializer(txn).data,
            },
            status=status.HTTP_201_CREATED,
        )