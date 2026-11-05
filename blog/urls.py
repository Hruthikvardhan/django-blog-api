"""Blog URL patterns (mounted under /api/ in config/urls.py)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

# SimpleRouter registers the fixed routes (my/, bookmarks/, trending/) BEFORE
# the /<slug>/ detail route, so they are never mistaken for slugs.
router = SimpleRouter()
router.register("posts", views.PostViewSet, basename="post")

urlpatterns = [
    *router.urls,
    path("posts/<slug:slug>/comments/", views.PostCommentListCreateView.as_view(), name="post-comments"),
    path("comments/<int:pk>/", views.CommentDetailView.as_view(), name="comment-detail"),
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("tags/", views.TagListView.as_view(), name="tag-list"),
]
