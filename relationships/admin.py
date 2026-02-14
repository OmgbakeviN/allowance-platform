from django.contrib import admin
from .models import ParentInvite, ParentStudentLink
# Register your models here.
@admin.register(ParentInvite)
class ParentInviteAdmin(admin.ModelAdmin):
    list_display = ["parent", "code", "student_email", "status", "expires_at", "created_at"]
    list_filter = ["status", "expires_at"]
    search_fields = ["code", "student_email"]
    ordering = ["-created_at"]

@admin.register(ParentStudentLink)
class ParentStudentLinkAdmin(admin.ModelAdmin):
    list_display = ["parent", "student", "status", "created_at", "revoked_at"]
    list_filter = ["status"]
    search_fields = ["parent__username", "student__username"]
    ordering = ["-created_at"]