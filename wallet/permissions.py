from rest_framework import permissions
from relationships.models import ParentStudentLink


def parent_can_access_student(parent, student_id: int) -> bool:
    if not parent or not parent.is_authenticated:
        return False
    if parent.is_superuser or getattr(parent, "role", None) == "ADMIN":
        return True
    if getattr(parent, "role", None) != "PARENT":
        return False
    return ParentStudentLink.objects.filter(
        parent=parent, student_id=student_id, status=ParentStudentLink.Status.ACTIVE
    ).exists()


class IsLinkedParent(permissions.BasePermission):
    def has_permission(self, request, view):
        student_id = view.kwargs.get("student_id")
        if student_id is None:
            return False
        return parent_can_access_student(request.user, int(student_id))
