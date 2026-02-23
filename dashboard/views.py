from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, inline_serializer

from accounts.permissions import IsStudent, IsParent
from wallet.permissions import IsLinkedParent
from .services import student_dashboard, parent_overview, parent_student_dashboard

User = get_user_model()

StudentDashboardSerializer = inline_serializer(
    name="StudentDashboard",
    fields={
        "wallet": serializers.DictField(),
        "spending": serializers.DictField(),
        "projection": serializers.DictField(),
        "top_categories": serializers.ListField(),
        "alerts": serializers.ListField(),
    },
)

ParentOverviewSerializer = inline_serializer(
    name="ParentOverviewDashboard",
    fields={
        "parent": serializers.DictField(),
        "total_sent_this_month": serializers.CharField(),
        "students": serializers.ListField(),
        "period": serializers.DictField(),
    },
)

ParentStudentDashboardSerializer = inline_serializer(
    name="ParentStudentDashboard",
    fields={
        "student": serializers.DictField(),
        "sent_this_month": serializers.CharField(),
        "repartition_this_month": serializers.ListField(),
        "wallet": serializers.DictField(),
        "spending": serializers.DictField(),
        "top_categories": serializers.ListField(),
        "alerts": serializers.ListField(),
    },
)


@extend_schema(
    tags=["Dashboard"],
    summary="Dashboard Étudiant",
    description=(
        "Retourne les indicateurs clés côté étudiant :\n"
        "- soldes (DAILY/SAVINGS/BILLS)\n"
        "- reste DAILY aujourd’hui (si daily_limit)\n"
        "- dépenses du jour + du mois\n"
        "- projection (recommandation par jour + burn rate 7 jours)\n"
        "- top catégories + alertes\n\n"
        "Filtres : `date_from/date_to` influencent surtout le top catégories."
    ),
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False, description="YYYY-MM-DD"),
        OpenApiParameter(name="date_to", type=str, required=False, description="YYYY-MM-DD"),
    ],
    responses={200: StudentDashboardSerializer},
    examples=[
        OpenApiExample(
            "Exemple",
            value={
                "wallet": {
                    "currency": "XAF",
                    "daily_limit": "2000.00",
                    "buckets": {"DAILY": "5000.00", "SAVINGS": "2000.00", "BILLS": "3000.00"},
                },
                "spending": {"spent_today": "1500.00", "daily_remaining_today": "500.00", "total_month_expenses": "8000.00"},
                "projection": {"days_left_in_month": 12, "recommended_daily_spend": "416.67", "avg_daily_spend_7d": "1200.00", "estimated_days_until_daily_empty": "4.17"},
                "top_categories": [],
                "alerts": [],
            },
            response_only=True,
        )
    ],
)
class StudentDashboardAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        df = parse_date(request.query_params.get("date_from") or "")
        dt = parse_date(request.query_params.get("date_to") or "")
        data = student_dashboard(request.user, date_from=df, date_to=dt)
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Dashboard"],
    summary="Dashboard Parent - Overview",
    description=(
        "Retourne un dashboard global pour le parent :\n"
        "- total envoyé ce mois\n"
        "- pour chaque étudiant lié : wallet + dépenses + alertes + répartition des dépôts.\n\n"
        "Filtres : `date_from/date_to` pour stats dépenses (top catégories)."
    ),
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False, description="YYYY-MM-DD"),
        OpenApiParameter(name="date_to", type=str, required=False, description="YYYY-MM-DD"),
    ],
    responses={200: ParentOverviewSerializer},
)
class ParentOverviewDashboardAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def get(self, request):
        df = parse_date(request.query_params.get("date_from") or "")
        dt = parse_date(request.query_params.get("date_to") or "")
        data = parent_overview(request.user, date_from=df, date_to=dt)
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Dashboard"],
    summary="Dashboard Parent - Étudiant lié",
    description=(
        "Dashboard détaillé pour un étudiant donné.\n"
        "Accessible seulement si le parent est lié à cet étudiant.\n\n"
        "Inclut :\n"
        "- envoyé ce mois + répartition (BILLS/SAVINGS/DAILY)\n"
        "- wallet (soldes)\n"
        "- dépenses + top catégories + alertes"
    ),
    parameters=[
        OpenApiParameter(name="date_from", type=str, required=False, description="YYYY-MM-DD"),
        OpenApiParameter(name="date_to", type=str, required=False, description="YYYY-MM-DD"),
    ],
    responses={200: ParentStudentDashboardSerializer},
)
class ParentStudentDashboardAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsLinkedParent]

    def get(self, request, student_id):
        student = User.objects.get(id=student_id)
        df = parse_date(request.query_params.get("date_from") or "")
        dt = parse_date(request.query_params.get("date_to") or "")
        data = parent_student_dashboard(request.user, student, date_from=df, date_to=dt)
        return Response(data, status=status.HTTP_200_OK)
