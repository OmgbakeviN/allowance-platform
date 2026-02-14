from rest_framework import permissions

def _is_role(user, roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, "role", None) in roles

class IsParent(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_role(request.user, {"PARENT", "ADMIN"})

class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_role(request.user, {"STUDENT", "ADMIN"})

class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_role(request.user, {"ADMIN"})
