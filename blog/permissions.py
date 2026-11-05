"""Object-level permissions."""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthorOrReadOnly(BasePermission):
    """Anyone may read; only the post's author may change or delete it."""

    message = "You do not have permission to modify this post."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class IsCommentOwnerOrAdminCanDelete(BasePermission):
    """
    Edit  -> comment author only.
    Delete -> comment author or an admin (is_staff).
    """

    message = "You do not have permission to modify this comment."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        is_owner = obj.author_id == request.user.id
        if request.method == "DELETE":
            return is_owner or request.user.is_staff
        return is_owner
