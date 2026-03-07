from django.urls import path
from .views import ParentAccountMeAPIView, ParentAccountTransactionsAPIView, ParentTopUpAPIView

urlpatterns = [
    path("me/", ParentAccountMeAPIView.as_view()),
    path("me/transactions/", ParentAccountTransactionsAPIView.as_view()),
    path("topup/", ParentTopUpAPIView.as_view()),
]