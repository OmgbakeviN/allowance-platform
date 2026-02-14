from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from accounts.permissions import IsParent, IsStudent
from .models import ParentInvite, ParentStudentLink
from .serializers import (
    InviteCreateSerializer,
    InviteSerializer,
    AcceptInviteSerializer,
    LinkSerializer,
)

class CreateInviteAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = InviteCreateSerializer

    def create(self, request, *args, **kwargs):
        invite = self.get_serializer(data=request.data)
        invite.is_valid(raise_exception=True)
        obj = invite.save()
        return Response(InviteSerializer(obj).data, status=status.HTTP_201_CREATED)

class MyInvitesAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = InviteSerializer

    def get_queryset(self):
        return ParentInvite.objects.filter(parent=self.request.user).order_by("-created_at")

class AcceptInviteAPIView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = AcceptInviteSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        link = s.save()
        return Response(LinkSerializer(link).data, status=status.HTTP_201_CREATED)

class ParentMyStudentsAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]
    serializer_class = LinkSerializer

    def get_queryset(self):
        return ParentStudentLink.objects.filter(
            parent=self.request.user, status=ParentStudentLink.Status.ACTIVE
        ).select_related("parent", "student").order_by("-created_at")

class StudentMyParentAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = LinkSerializer

    def get_object(self):
        return ParentStudentLink.objects.select_related("parent", "student").get(
            student=self.request.user, status=ParentStudentLink.Status.ACTIVE
        )

class RevokeStudentLinkAPIView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def delete(self, request, student_id, *args, **kwargs):
        with transaction.atomic():
            link = ParentStudentLink.objects.select_for_update().get(
                parent=request.user, student_id=student_id, status=ParentStudentLink.Status.ACTIVE
            )
            link.status = ParentStudentLink.Status.REVOKED
            link.revoked_at = timezone.now()
            link.save(update_fields=["status", "revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
