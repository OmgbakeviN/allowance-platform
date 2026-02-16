from django.urls import path
from .views import (
    WalletMeAPIView,
    WalletMeSettingsAPIView,
    WalletMeTransactionsAPIView,
    WalletStudentAPIView,
    WalletStudentTransactionsAPIView,
    DepositAPIView,
    ExpenseAPIView,
)

urlpatterns = [
    path("me/", WalletMeAPIView.as_view()),
    path("me/settings/", WalletMeSettingsAPIView.as_view()),
    path("me/transactions/", WalletMeTransactionsAPIView.as_view()),
    path("students/<int:student_id>/", WalletStudentAPIView.as_view()),
    path("students/<int:student_id>/transactions/", WalletStudentTransactionsAPIView.as_view()),
    path("deposits/", DepositAPIView.as_view()),
    path("expenses/", ExpenseAPIView.as_view()),
]
