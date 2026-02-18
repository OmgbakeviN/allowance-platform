from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, inline_serializer
from rest_framework import serializers

from accounts.permissions import IsStudent
from wallet.permissions import IsLinkedParent
from relationships.models import ParentStudentLink

from .models import Expense, ExpenseCategory
from .serializers import (
    ExpenseCategorySerializer,
    CategoryCreateSerializer,
    ExpenseCreateSerializer,
    ExpenseListSerializer,
)
from .services import categories_for_student, summary_for_student

User = get_user_model()


SummarySerializer = inline_serializer(
    name="ExpenseSummary",
    fields={
        "total_today": serializers.CharField(),
        "total_week": serializers.CharField(),
        "total_month": serializers.CharField(),
        "top_categories": serializers.ListField(),
        "alerts": serializers.ListField(),
    },
)


@extend_schema(
    tags=["Expenses"],
    summary="Lister mes catégories (Étudiant)",
    description=(
        "Retourne les catégories disponibles pour l’étudiant :\n"
        "- catégories par défaut (globales)\n"
        "- catégories personnalisées créées par l’étudiant"
    ),
    responses={200: ExpenseCategorySerializer(many=True)},
)
class StudentCategoryListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ExpenseCategorySerializer

    def get_queryset(self):
        return categories_for_student(self.request.user).order_by("is_default", "name")


@extend_schema(
    tags=["Expenses"],
    summary="Créer une catégorie personnalisée (Étudiant)",
    description=(
        "Crée une catégorie personnelle (ex: 'Snack', 'Data Bundle').\n"
        "Le `slug` doit être unique pour cet étudiant."
    ),
    request=CategoryCreateSerializer,
    responses={201: ExpenseCategorySerializer},
    examples=[
        OpenApiExample(
            "Créer catégorie",
            value={"name": "Snack", "slug": "snack"},
            request_only=True,
        )
    ],
)
class StudentCategoryCreateAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = CategoryCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cat = serializer.save()
        return Response(ExpenseCategorySerializer(cat).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Expenses"],
    summary="Créer une dépense (Étudiant)",
    description=(
        "Enregistre une dépense et crée automatiquement une transaction (DEBIT / EXPENSE) dans le wallet.\n\n"
        "Champs :\n"
        "- `amount`, `bucket_type` (DAILY par défaut)\n"
        "- `category_id` ou `category_slug`\n"
        "- `note` (description)\n"
        "- `receipt` (optionnel - V2)\n\n"
        "Règles :\n"
        "- solde suffisant dans l’enveloppe\n"
        "- si DAILY + daily_limit > 0 : ne doit pas dépasser le plafond du jour"
    ),
    request=ExpenseCreateSerializer,
    responses={201: ExpenseListSerializer},
    examples=[
        OpenApiExample(
            "Dépense simple",
            value={"amount": "1500.00", "bucket_type": "DAILY", "category_slug": "food", "note": "Lunch"},
            request_only=True,
        )
    ],
)
class StudentExpenseCreateAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ExpenseCreateSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        exp = s.save()
        return Response(ExpenseListSerializer(exp).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Expenses"],
    summary="Lister mes dépenses (Étudiant)",
    description=(
        "Liste les dépenses de l’étudiant connecté.\n\n"
        "Filtres (query params) :\n"
        "- `date_from=YYYY-MM-DD`\n"
        "- `date_to=YYYY-MM-DD`\n"
        "- `category_id=<id>`\n"
        "- `bucket_type=DAILY|BILLS|SAVINGS`"
    ),
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False),
        OpenApiParameter(name="date_to", type=str, required=False),
        OpenApiParameter(name="category_id", type=int, required=False),
        OpenApiParameter(name="bucket_type", type=str, required=False),
    ],
    responses={200: ExpenseListSerializer(many=True)},
)
class StudentExpenseListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ExpenseListSerializer

    def get_queryset(self):
        qs = Expense.objects.filter(student=self.request.user).select_related("category").order_by("-occurred_at")

        df = parse_date(self.request.query_params.get("date_from") or "")
        dt = parse_date(self.request.query_params.get("date_to") or "")
        cid = self.request.query_params.get("category_id")
        bt = self.request.query_params.get("bucket_type")

        if df:
            qs = qs.filter(occurred_at__date__gte=df)
        if dt:
            qs = qs.filter(occurred_at__date__lte=dt)
        if cid:
            qs = qs.filter(category_id=cid)
        if bt:
            qs = qs.filter(bucket_type=bt)

        return qs


@extend_schema(
    tags=["Expenses"],
    summary="Résumé dépenses + top catégories + alertes (Étudiant)",
    description=(
        "Retourne un résumé :\n"
        "- total_today / total_week / total_month\n"
        "- top 5 catégories (somme)\n"
        "- alertes (ex: near daily limit)"
    ),
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False, description="Appliqué uniquement au top catégories"),
        OpenApiParameter(name="date_to", type=str, required=False, description="Appliqué uniquement au top catégories"),
    ],
    responses={200: SummarySerializer},
)
class StudentExpenseSummaryAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        df = parse_date(request.query_params.get("date_from") or "")
        dt = parse_date(request.query_params.get("date_to") or "")
        data = summary_for_student(request.user, date_from=df, date_to=dt)
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Expenses"],
    summary="Lister les dépenses d’un étudiant lié (Parent)",
    description=(
        "Permet au parent de consulter les dépenses d’un étudiant **uniquement s’ils sont liés**.\n"
        "Filtres identiques à l’endpoint étudiant."
    ),
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False),
        OpenApiParameter(name="date_to", type=str, required=False),
        OpenApiParameter(name="category_id", type=int, required=False),
        OpenApiParameter(name="bucket_type", type=str, required=False),
    ],
    responses={200: ExpenseListSerializer(many=True)},
)
class ParentStudentExpenseListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsLinkedParent]
    serializer_class = ExpenseListSerializer

    def get_queryset(self):
        student = User.objects.get(id=self.kwargs["student_id"])
        qs = Expense.objects.filter(student=student).select_related("category").order_by("-occurred_at")

        df = parse_date(self.request.query_params.get("date_from") or "")
        dt = parse_date(self.request.query_params.get("date_to") or "")
        cid = self.request.query_params.get("category_id")
        bt = self.request.query_params.get("bucket_type")

        if df:
            qs = qs.filter(occurred_at__date__gte=df)
        if dt:
            qs = qs.filter(occurred_at__date__lte=dt)
        if cid:
            qs = qs.filter(category_id=cid)
        if bt:
            qs = qs.filter(bucket_type=bt)

        return qs


@extend_schema(
    tags=["Expenses"],
    summary="Résumé + top catégories + alertes d’un étudiant lié (Parent)",
    description="Même résumé que côté étudiant, mais accessible au parent si lien actif.",
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False),
        OpenApiParameter(name="date_to", type=str, required=False),
    ],
    responses={200: SummarySerializer},
)
class ParentStudentExpenseSummaryAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsLinkedParent]

    def get(self, request, student_id):
        student = User.objects.get(id=student_id)
        df = parse_date(request.query_params.get("date_from") or "")
        dt = parse_date(request.query_params.get("date_to") or "")
        data = summary_for_student(student, date_from=df, date_to=dt)
        return Response(data, status=status.HTTP_200_OK)
