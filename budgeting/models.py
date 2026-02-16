from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class BudgetPlan(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class SavingsMode(models.TextChoices):
        NONE = "NONE", "None"
        AMOUNT = "AMOUNT", "Fixed amount"
        PERCENT = "PERCENT", "Percent"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="budget_plans")
    name = models.CharField(max_length=80, default="My Monthly Plan")
    currency = models.CharField(max_length=8, default="XAF")
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    savings_mode = models.CharField(max_length=10, choices=SavingsMode.choices, default=SavingsMode.NONE)
    savings_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    savings_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["student", "status", "created_at"])]

    def __str__(self):
        return f"Plan({self.student_id},{self.status})"


class BillItem(models.Model):
    plan = models.ForeignKey(BudgetPlan, on_delete=models.CASCADE, related_name="bills")
    title = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_day = models.PositiveSmallIntegerField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=1)
    is_mandatory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["plan", "priority"])]

    def __str__(self):
        return f"Bill({self.plan_id}:{self.title})"
