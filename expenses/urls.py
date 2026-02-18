from django.urls import path
from .views import (
    StudentCategoryListAPIView,
    StudentCategoryCreateAPIView,
    StudentExpenseCreateAPIView,
    StudentExpenseListAPIView,
    StudentExpenseSummaryAPIView,
    ParentStudentExpenseListAPIView,
    ParentStudentExpenseSummaryAPIView,
)

urlpatterns = [
    path("categories/", StudentCategoryListAPIView.as_view()),
    path("categories/create/", StudentCategoryCreateAPIView.as_view()),

    path("me/", StudentExpenseListAPIView.as_view()),
    path("me/create/", StudentExpenseCreateAPIView.as_view()),
    path("me/summary/", StudentExpenseSummaryAPIView.as_view()),

    path("students/<int:student_id>/", ParentStudentExpenseListAPIView.as_view()),
    path("students/<int:student_id>/summary/", ParentStudentExpenseSummaryAPIView.as_view()),
]
