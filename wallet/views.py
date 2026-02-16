from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer

from accounts.permissions import IsStudent, IsParent
from .permissions import IsLinkedParent
from .models import Wallet, WalletTransaction
from .serializers import (
    WalletSerializer,
    WalletTransactionSerializer,
    WalletSettingsUpdateSerializer,
    DepositSerializer,
    ExpenseSerializer,
)
from .services import get_or_create_wallet_for_student

User = get_user_model()

DepositResponseSerializer = inline_serializer(
    name="DepositResponse",
    fields={
        "wallet": WalletSerializer(),
        "transactions": WalletTransactionSerializer(many=True),
    },
)

ExpenseResponseSerializer = inline_serializer(
    name="ExpenseResponse",
    fields={
        "wallet": WalletSerializer(),
        "transaction": WalletTransactionSerializer(),
    },
)


@extend_schema(
    tags=["Wallet"],
    summary="Récupérer mon wallet (Étudiant)",
    description=(
        "Retourne le wallet de l'étudiant connecté, incluant les soldes par enveloppe (BILLS / SAVINGS / DAILY).\n\n"
        "Si le wallet n'existe pas encore, il est créé automatiquement (avec ses 3 enveloppes)."
    ),
    responses={200: WalletSerializer},
    examples=[
        OpenApiExample(
            "Réponse (exemple)",
            value={
                "id": 1,
                "currency": "XAF",
                "daily_limit": "2000.00",
                "created_at": "2026-02-16T08:30:00Z",
                "buckets": [
                    {"bucket_type": "BILLS", "balance": "3000.00", "updated_at": "2026-02-16T08:40:00Z"},
                    {"bucket_type": "SAVINGS", "balance": "2000.00", "updated_at": "2026-02-16T08:40:00Z"},
                    {"bucket_type": "DAILY", "balance": "5000.00", "updated_at": "2026-02-16T08:40:00Z"},
                ],
            },
            response_only=True,
        )
    ],
)
class WalletMeAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = WalletSerializer

    def get_object(self):
        wallet = get_or_create_wallet_for_student(self.request.user)
        return Wallet.objects.prefetch_related("buckets").get(id=wallet.id)


@extend_schema(
    tags=["Wallet"],
    summary="Mettre à jour mes paramètres wallet (Étudiant)",
    description=(
        "Permet à l'étudiant de configurer :\n"
        "- `currency` (ex: XAF, USD)\n"
        "- `daily_limit` (plafond de dépense journalier appliqué sur l’enveloppe DAILY)\n\n"
        "⚠️ `daily_limit` = 0 signifie : pas de limite."
    ),
    request=WalletSettingsUpdateSerializer,
    responses={200: WalletSettingsUpdateSerializer},
    examples=[
        OpenApiExample(
            "Requête (exemple)",
            value={"currency": "XAF", "daily_limit": "2000.00"},
            request_only=True,
        ),
    ],
)
class WalletMeSettingsAPIView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = WalletSettingsUpdateSerializer

    def get_object(self):
        return get_or_create_wallet_for_student(self.request.user)


@extend_schema(
    tags=["Wallet"],
    summary="Lister mes transactions (Étudiant)",
    description=(
        "Retourne l'historique des transactions du wallet de l'étudiant (ledger), trié par date décroissante.\n\n"
        "Types usuels :\n"
        "- CREDIT / DEBIT\n"
        "- txn_type : DEPOSIT, ALLOCATION, EXPENSE, ADJUSTMENT\n\n"
        "NB : pas de filtres dans ce MVP (tu peux les ajouter plus tard via query params)."
    ),
    responses={200: WalletTransactionSerializer(many=True)},
)
class WalletMeTransactionsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        wallet = get_or_create_wallet_for_student(self.request.user)
        return WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")


@extend_schema(
    tags=["Wallet"],
    summary="Récupérer le wallet d'un étudiant lié (Parent)",
    description=(
        "Permet à un parent de récupérer le wallet d’un étudiant **uniquement s’ils sont liés** "
        "(ParentStudentLink actif).\n\n"
        "Retourne les enveloppes et soldes (BILLS / SAVINGS / DAILY)."
    ),
    responses={200: WalletSerializer},
)
class WalletStudentAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsLinkedParent]
    serializer_class = WalletSerializer

    def get_object(self):
        student = User.objects.get(id=self.kwargs["student_id"])
        wallet = get_or_create_wallet_for_student(student)
        return Wallet.objects.prefetch_related("buckets").get(id=wallet.id)


@extend_schema(
    tags=["Wallet"],
    summary="Lister les transactions d'un étudiant lié (Parent)",
    description=(
        "Permet à un parent de consulter l'historique des transactions (ledger) d’un étudiant "
        "**uniquement s'ils sont liés**.\n\n"
        "Tri : date décroissante."
    ),
    responses={200: WalletTransactionSerializer(many=True)},
)
class WalletStudentTransactionsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsLinkedParent]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        student = User.objects.get(id=self.kwargs["student_id"])
        wallet = get_or_create_wallet_for_student(student)
        return WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")


@extend_schema(
    tags=["Wallet"],
    summary="Dépôt parent vers étudiant (allocation automatique)",
    description=(
        "Crée un dépôt sur le wallet d’un étudiant lié et **répartit automatiquement** selon le plan actif de l’étudiant.\n\n"
        "Ordre d’allocation :\n"
        "1) **BILLS** (charges fixes, par priorité)\n"
        "2) **SAVINGS** (selon `savings_mode`: AMOUNT ou PERCENT)\n"
        "3) **DAILY** (le reste)\n\n"
        "Si l’étudiant **n’a pas de plan actif**, le dépôt va **100% dans DAILY**.\n\n"
        "⚠️ `external_ref` sert de référence (et est suffixé automatiquement par bucket : -BILLS/-SAVINGS/-DAILY)."
    ),
    request=DepositSerializer,
    responses={201: DepositResponseSerializer},
    examples=[
        OpenApiExample(
            "Requête (allocation automatique)",
            value={
                "student_id": 2,
                "amount": "10000.00",
                "description": "Allowance February",
                "external_ref": "DEP-0003",
            },
            request_only=True,
        ),
    ],
)
class DepositAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = DepositSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        wallet, txns = s.save()
        wallet = Wallet.objects.prefetch_related("buckets").get(id=wallet.id)
        return Response(
            {"wallet": WalletSerializer(wallet).data, "transactions": WalletTransactionSerializer(txns, many=True).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Wallet"],
    summary="Enregistrer une dépense (Étudiant)",
    description=(
        "Débite une enveloppe (`bucket_type`) du wallet de l’étudiant.\n\n"
        "Règles :\n"
        "- Le solde de l’enveloppe doit être suffisant (sinon erreur).\n"
        "- Si `bucket_type = DAILY` et `daily_limit > 0`, la dépense ne doit pas faire dépasser le plafond du jour.\n\n"
        "Retourne le wallet mis à jour + la transaction créée."
    ),
    request=ExpenseSerializer,
    responses={201: ExpenseResponseSerializer},
    examples=[
        OpenApiExample(
            "Requête (exemple)",
            value={"amount": "1500.00", "bucket_type": "DAILY", "description": "Lunch"},
            request_only=True,
        ),
    ],
)
class ExpenseAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ExpenseSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        wallet, txn = s.save()
        wallet = Wallet.objects.prefetch_related("buckets").get(id=wallet.id)
        return Response(
            {"wallet": WalletSerializer(wallet).data, "transaction": WalletTransactionSerializer(txn).data},
            status=status.HTTP_201_CREATED,
        )
