from django.contrib import admin
from .models import BudgetPlan, BillItem

admin.site.register(BudgetPlan)
admin.site.register(BillItem)
