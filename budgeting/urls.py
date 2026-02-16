from django.urls import path
from .views import (
    StudentPlanListAPIView,
    StudentPlanCreateAPIView,
    StudentActivePlanAPIView,
    StudentPlanDetailUpdateAPIView,
    StudentPlanActivateAPIView,
    StudentPlanBillsListCreateAPIView,
    StudentBillItemDetailAPIView,
    ParentStudentActivePlanAPIView,
)

urlpatterns = [
    path("plans/me/", StudentPlanListAPIView.as_view()),
    path("plans/", StudentPlanCreateAPIView.as_view()),
    path("plans/active/", StudentActivePlanAPIView.as_view()),
    path("plans/<int:pk>/", StudentPlanDetailUpdateAPIView.as_view()),
    path("plans/<int:plan_id>/activate/", StudentPlanActivateAPIView.as_view()),
    path("plans/<int:plan_id>/bills/", StudentPlanBillsListCreateAPIView.as_view()),
    path("bills/<int:pk>/", StudentBillItemDetailAPIView.as_view()),
    path("students/<int:student_id>/plans/active/", ParentStudentActivePlanAPIView.as_view()),
]
