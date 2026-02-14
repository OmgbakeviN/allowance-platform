from django.urls import path
from .views import (
    CreateInviteAPIView,
    MyInvitesAPIView,
    AcceptInviteAPIView,
    ParentMyStudentsAPIView,
    StudentMyParentAPIView,
    RevokeStudentLinkAPIView,
)

urlpatterns = [
    path("invites/", CreateInviteAPIView.as_view()),
    path("invites/me/", MyInvitesAPIView.as_view()),
    path("invites/accept/", AcceptInviteAPIView.as_view()),
    path("links/parent/students/", ParentMyStudentsAPIView.as_view()),
    path("links/student/parent/", StudentMyParentAPIView.as_view()),
    path("links/parent/revoke/<int:student_id>/", RevokeStudentLinkAPIView.as_view()),
]
