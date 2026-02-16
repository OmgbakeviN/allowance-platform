from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer

from accounts.permissions import IsStudent
from relationships.models import ParentStudentLink
from wallet.permissions import IsLinkedParent
from .models import BudgetPlan, BillItem
from .serializers import (
    BudgetPlanCreateUpdateSerializer,
    BudgetPlanDetailSerializer,
    BillItemSerializer,
)

User = get_user_model()

ActivateResponseSerializer = inline_serializer(
    name="ActivatePlanResponse",
    fields={
        "active_plan_id": inline_serializer(name="ActivePlanId", fields={}).fields.get,  # placeholder not used
    },
)


def _student_active_plan(student):
    return BudgetPlan.objects.filter(student=student, status=BudgetPlan.Status.ACTIVE).order_by("-created_at").first()


@extend_schema(
    tags=["Budgeting"],
    summary="Lister mes plans de budget (Étudiant)",
    description=(
        "Retourne tous les plans de budget créés par l’étudiant connecté.\n\n"
        "Un seul plan peut être **ACTIVE** à la fois. Les autres restent **INACTIVE**."
    ),
    responses={200: BudgetPlanCreateUpdateSerializer(many=True)},
)
class StudentPlanListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = BudgetPlanCreateUpdateSerializer

    def get_queryset(self):
        return BudgetPlan.objects.filter(student=self.request.user).order_by("-created_at")


@extend_schema(
    tags=["Budgeting"],
    summary="Créer un nouveau plan de budget (Étudiant)",
    description=(
        "Crée un plan **INACTIVE** par défaut (tu l’activeras ensuite).\n\n"
        "Champs importants :\n"
        "- `daily_limit`: plafond quotidien (0 = pas de limite)\n"
        "- `savings_mode`: NONE / AMOUNT / PERCENT\n"
        "- `savings_amount` ou `savings_percent` selon le mode"
    ),
    request=BudgetPlanCreateUpdateSerializer,
    responses={201: BudgetPlanCreateUpdateSerializer},
    examples=[
        OpenApiExample(
            "Créer un plan (AMOUNT)",
            value={
                "name": "Plan Février",
                "currency": "XAF",
                "daily_limit": "2000.00",
                "savings_mode": "AMOUNT",
                "savings_amount": "15000.00",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Créer un plan (PERCENT)",
            value={
                "name": "Plan Mars",
                "currency": "XAF",
                "daily_limit": "3000.00",
                "savings_mode": "PERCENT",
                "savings_percent": "10.00",
            },
            request_only=True,
        ),
    ],
)
class StudentPlanCreateAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = BudgetPlanCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


@extend_schema(
    tags=["Budgeting"],
    summary="Récupérer mon plan actif (Étudiant)",
    description=(
        "Retourne le plan actuellement **ACTIVE** de l’étudiant, avec la liste des charges fixes (`bills`).\n\n"
        "Si aucun plan n’est actif, retourne 404."
    ),
    responses={200: BudgetPlanDetailSerializer},
)
class StudentActivePlanAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = BudgetPlanDetailSerializer

    def get_object(self):
        plan = BudgetPlan.objects.prefetch_related("bills").filter(
            student=self.request.user, status=BudgetPlan.Status.ACTIVE
        ).order_by("-created_at").first()
        if not plan:
            from rest_framework.exceptions import NotFound
            raise NotFound("No active plan.")
        return plan


@extend_schema(
    tags=["Budgeting"],
    summary="Détails / Modifier un plan (Étudiant)",
    description=(
        "Permet à l’étudiant de consulter ou modifier un plan donné (le plan doit lui appartenir).\n\n"
        "NB : Dans ce MVP, modifier un plan ACTIVE est autorisé. Si tu veux être strict, on peut bloquer "
        "les modifications et forcer la création d’une nouvelle version."
    ),
    responses={200: BudgetPlanDetailSerializer},
)
class StudentPlanDetailUpdateAPIView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return BudgetPlan.objects.filter(student=self.request.user).prefetch_related("bills")

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return BudgetPlanCreateUpdateSerializer
        return BudgetPlanDetailSerializer


@extend_schema(
    tags=["Budgeting"],
    summary="Activer un plan (Étudiant)",
    description=(
        "Active le plan sélectionné et désactive tous les autres plans de l’étudiant.\n\n"
        "Retour : l’ID du plan activé."
    ),
    request=None,
    responses={
        200: inline_serializer(
            name="ActivatePlanResult",
            fields={"active_plan_id": inline_serializer(name="IdField", fields={}).fields.get},
        )
    },
)
class StudentPlanActivateAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, plan_id):
        with transaction.atomic():
            plan = BudgetPlan.objects.select_for_update().get(id=plan_id, student=request.user)
            BudgetPlan.objects.filter(student=request.user, status=BudgetPlan.Status.ACTIVE).update(
                status=BudgetPlan.Status.INACTIVE
            )
            plan.status = BudgetPlan.Status.ACTIVE
            plan.save(update_fields=["status", "updated_at"])

        return Response({"active_plan_id": plan.id}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Budgeting"],
    summary="Lister / Ajouter des charges fixes (Étudiant)",
    description=(
        "Gère les charges fixes (`BillItem`) d’un plan donné.\n\n"
        "- GET : liste des bills\n"
        "- POST : ajoute une bill\n\n"
        "Champs :\n"
        "- `title`, `amount`\n"
        "- `due_day` (1..31 optionnel)\n"
        "- `priority` (ordre d’allocation plus tard)\n"
        "- `is_mandatory`"
    ),
    responses={200: BillItemSerializer(many=True), 201: BillItemSerializer},
    examples=[
        OpenApiExample(
            "Ajouter une charge (exemple)",
            value={"title": "Loyer", "amount": "30000.00", "due_day": 5, "priority": 1, "is_mandatory": True},
            request_only=True,
        )
    ],
)
class StudentPlanBillsListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = BillItemSerializer

    def get_plan(self):
        return BudgetPlan.objects.get(id=self.kwargs["plan_id"], student=self.request.user)

    def get_queryset(self):
        plan = self.get_plan()
        return BillItem.objects.filter(plan=plan).order_by("priority", "created_at")

    def perform_create(self, serializer):
        plan = self.get_plan()
        serializer.save(plan=plan)


@extend_schema(
    tags=["Budgeting"],
    summary="Modifier / Supprimer une charge fixe (Étudiant)",
    description=(
        "Permet de modifier ou supprimer une charge fixe appartenant à un plan de l’étudiant.\n\n"
        "- PATCH : modifier\n"
        "- DELETE : supprimer"
    ),
    responses={200: BillItemSerializer},
)
class StudentBillItemDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = BillItemSerializer

    def get_queryset(self):
        return BillItem.objects.filter(plan__student=self.request.user)


@extend_schema(
    tags=["Budgeting"],
    summary="Voir le plan actif d’un étudiant lié (Parent)",
    description=(
        "Retourne le plan **ACTIVE** de l’étudiant ciblé, uniquement si le parent est lié (ParentStudentLink actif).\n\n"
        "Lecture seule."
    ),
    responses={200: BudgetPlanDetailSerializer},
)
class ParentStudentActivePlanAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsLinkedParent]
    serializer_class = BudgetPlanDetailSerializer

    def get_object(self):
        student = User.objects.get(id=self.kwargs["student_id"])
        plan = BudgetPlan.objects.prefetch_related("bills").filter(
            student=student, status=BudgetPlan.Status.ACTIVE
        ).order_by("-created_at").first()
        if not plan:
            from rest_framework.exceptions import NotFound
            raise NotFound("Student has no active plan.")
        return plan
