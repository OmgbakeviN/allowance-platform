from django.urls import path
from .views import (
    StudentDashboardAPIView,
    ParentOverviewDashboardAPIView,
    ParentStudentDashboardAPIView,
)

urlpatterns = [
    path("student/", StudentDashboardAPIView.as_view()),
    path("parent/overview/", ParentOverviewDashboardAPIView.as_view()),
    path("parent/students/<int:student_id>/", ParentStudentDashboardAPIView.as_view()),
]
