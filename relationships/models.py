import secrets
import string
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class ParentInvite(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        USED = "USED", "Used"
        REVOKED = "REVOKED", "Revoked"
        EXPIRED = "EXPIRED", "Expired"

    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invites")
    code = models.CharField(max_length=12, unique=True, db_index=True)
    student_email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)

        if not self.code:
            alphabet = string.ascii_uppercase + string.digits
            for _ in range(20):
                candidate = "".join(secrets.choice(alphabet) for _ in range(10))
                if not ParentInvite.objects.filter(code=candidate).exists():
                    self.code = candidate
                    break
            if not self.code:
                self.code = secrets.token_hex(6).upper()

        if self.status == self.Status.PENDING and self.is_expired():
            self.status = self.Status.EXPIRED

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent_id} - {self.code} - {self.status}"


class ParentStudentLink(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"

    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="linked_students")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="linked_parent")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["parent", "student"], name="uniq_parent_student"),
        ]

    def __str__(self):
        return f"{self.parent_id} -> {self.student_id} ({self.status})"
