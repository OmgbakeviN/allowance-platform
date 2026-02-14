from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import ParentInvite, ParentStudentLink

User = get_user_model()

class InviteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentInvite
        fields = ["student_email"]

    def create(self, validated_data):
        parent = self.context["request"].user
        return ParentInvite.objects.create(parent=parent, **validated_data)

class InviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentInvite
        fields = ["code", "status", "expires_at", "student_email", "created_at"]

class AcceptInviteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)

    @transaction.atomic
    def create(self, validated_data):
        student = self.context["request"].user
        code = validated_data["code"].strip().upper()

        try:
            invite = ParentInvite.objects.select_for_update().get(code=code)
        except ParentInvite.DoesNotExist:
            raise serializers.ValidationError({"code": "Invalid code."})

        if invite.status != ParentInvite.Status.PENDING:
            raise serializers.ValidationError({"code": f"Invite not usable ({invite.status})."})

        if invite.is_expired():
            invite.status = ParentInvite.Status.EXPIRED
            invite.save(update_fields=["status"])
            raise serializers.ValidationError({"code": "Invite expired."})

        if getattr(invite.parent, "role", None) not in {"PARENT", "ADMIN"} and not invite.parent.is_superuser:
            raise serializers.ValidationError({"code": "Invalid inviter role."})

        if getattr(student, "role", None) not in {"STUDENT", "ADMIN"} and not student.is_superuser:
            raise serializers.ValidationError({"code": "Only students can accept invites."})

        existing_active = ParentStudentLink.objects.filter(student=student, status=ParentStudentLink.Status.ACTIVE).exists()
        if existing_active:
            raise serializers.ValidationError({"code": "Student already linked to a parent."})

        link, _ = ParentStudentLink.objects.get_or_create(parent=invite.parent, student=student)
        link.status = ParentStudentLink.Status.ACTIVE
        link.revoked_at = None
        link.save(update_fields=["status", "revoked_at"])

        invite.status = ParentInvite.Status.USED
        invite.used_at = timezone.now()
        invite.save(update_fields=["status", "used_at"])

        return link

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "first_name", "last_name"]

class LinkSerializer(serializers.ModelSerializer):
    parent = UserMiniSerializer()
    student = UserMiniSerializer()

    class Meta:
        model = ParentStudentLink
        fields = ["id", "parent", "student", "status", "created_at", "revoked_at"]
