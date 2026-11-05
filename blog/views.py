"""Blog API views: posts, comments, categories, tags."""
from datetime import timedelta

from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .filters import PostFilter
from .models import Category, Comment, Post, Tag
from .permissions import IsAuthorOrReadOnly, IsCommentOwnerOrAdminCanDelete
from .serializers import (
    CategorySerializer,
    CommentSerializer,
    CommentUpdateSerializer,
    PostDetailSerializer,
    PostListSerializer,
    PostWriteSerializer,
    TagSerializer,
)

TRENDING_DAYS = 7
TRENDING_LIMIT = 10


def visible_posts(user):
    """Published posts for everyone, plus the user's own drafts when logged in."""
    qs = Post.objects.all()
    if user.is_authenticated:
        return qs.filter(Q(status=Post.Status.PUBLISHED) | Q(author=user))
    return qs.published()


class PostViewSet(viewsets.ModelViewSet):
    """
    /api/posts/                list (published) / create
    /api/posts/<slug>/         retrieve (+1 view) / update / delete
    /api/posts/my/             my posts incl. drafts
    /api/posts/bookmarks/      my bookmarks
    /api/posts/trending/       top 10 by views + likes, last 7 days
    /api/posts/<slug>/like/    toggle like
    /api/posts/<slug>/bookmark/ toggle bookmark
    """

    lookup_field = "slug"
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # multipart for featured_image
    filterset_class = PostFilter
    ordering_fields = ["published_at", "view_count", "created_at", "like_count", "comment_count"]
    ordering = ["-published_at", "-created_at"]

    # ------------------------------------------------------------ plumbing
    def get_permissions(self):
        if self.action in ("list", "retrieve", "trending"):
            return [AllowAny()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsAuthorOrReadOnly()]
        return [IsAuthenticated()]  # create, my, bookmarks, like, bookmark

    def get_queryset(self):
        user = self.request.user
        qs = Post.objects.with_stats(user)

        if self.action == "list":
            return qs.published()
        if self.action == "my":
            return qs.filter(author=user)
        if self.action == "bookmarks":
            return qs.published().filter(pk__in=user.bookmarked_posts.values("pk"))
        if self.action == "trending":
            return qs.published()
        # retrieve / update / delete / like / bookmark: published, or my own draft
        if user.is_authenticated:
            return qs.filter(Q(status=Post.Status.PUBLISHED) | Q(author=user))
        return qs.published()

    def get_serializer_class(self):
        if self.action in ("list", "my", "bookmarks", "trending"):
            return PostListSerializer
        if self.action in ("create", "update", "partial_update"):
            return PostWriteSerializer
        return PostDetailSerializer

    def _detail_response(self, pk: int, status_code: int = status.HTTP_200_OK) -> Response:
        """Re-fetch with annotations so write responses look like GET responses."""
        post = Post.objects.with_stats(self.request.user).get(pk=pk)
        data = PostDetailSerializer(post, context=self.get_serializer_context()).data
        return Response(data, status=status_code)

    # ---------------------------------------------------------------- CRUD
    def create(self, request, *args, **kwargs) -> Response:
        serializer = PostWriteSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        post = serializer.save(author=request.user)
        return self._detail_response(post.pk, status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs) -> Response:
        post = self.get_object()
        # Atomic increment in the database (no race conditions).
        Post.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        post.view_count += 1
        return Response(self.get_serializer(post).data)

    def update(self, request, *args, **kwargs) -> Response:
        partial = kwargs.pop("partial", False)
        post = self.get_object()  # raises 403 for non-authors
        serializer = PostWriteSerializer(
            post, data=request.data, partial=partial, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return self._detail_response(post.pk)

    # ------------------------------------------------------- list-style extras
    def _paginated(self, request, queryset) -> Response:
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def my(self, request) -> Response:
        """My posts, drafts included (newest first unless ?ordering= is given)."""
        qs = self.filter_queryset(self.get_queryset())
        if "ordering" not in request.query_params:
            qs = qs.order_by("-created_at")
        return self._paginated(request, qs)

    @action(detail=False, methods=["get"])
    def bookmarks(self, request) -> Response:
        """Posts I bookmarked."""
        return self._paginated(request, self.filter_queryset(self.get_queryset()))

    @action(detail=False, methods=["get"])
    def trending(self, request) -> Response:
        """Top 10 posts published in the last 7 days ranked by views + likes."""
        since = timezone.now() - timedelta(days=TRENDING_DAYS)
        posts = (
            self.get_queryset()
            .filter(published_at__gte=since)
            .annotate(score=F("view_count") + F("like_count"))
            .order_by("-score", "-published_at")[:TRENDING_LIMIT]
        )
        return Response(self.get_serializer(posts, many=True).data)

    # ------------------------------------------------------------ toggles
    def _toggle(self, request, field: str) -> tuple[bool, int]:
        """Add the user to the M2M field if absent, else remove. Returns (now_active, total)."""
        post = self.get_object()
        relation = getattr(post, field)
        if relation.filter(pk=request.user.pk).exists():
            relation.remove(request.user)
            active = False
        else:
            relation.add(request.user)
            active = True
        return active, relation.count()

    @action(detail=True, methods=["post"])
    def like(self, request, slug=None) -> Response:
        """Toggle like on a post."""
        liked, count = self._toggle(request, "likes")
        return Response({"liked": liked, "like_count": count})

    @action(detail=True, methods=["post"])
    def bookmark(self, request, slug=None) -> Response:
        """Toggle bookmark on a post."""
        bookmarked, count = self._toggle(request, "bookmarks")
        return Response({"bookmarked": bookmarked, "bookmark_count": count})


# ---------------------------------------------------------------- comments
class PostCommentListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/posts/<slug>/comments/  top-level comments with nested replies
    POST /api/posts/<slug>/comments/  {"content": "...", "parent": <id optional>}
    """

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_post(self) -> Post:
        if not hasattr(self, "_post"):
            self._post = get_object_or_404(visible_posts(self.request.user), slug=self.kwargs["slug"])
        return self._post

    def get_queryset(self):
        replies = Prefetch(
            "replies", queryset=Comment.objects.select_related("author").order_by("created_at")
        )
        return (
            Comment.objects.filter(post=self.get_post(), parent__isnull=True)
            .select_related("author")
            .prefetch_related(replies)
            .order_by("created_at")
        )

    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        context["post"] = self.get_post()
        return context

    def perform_create(self, serializer) -> None:
        serializer.save(post=self.get_post(), author=self.request.user)


class CommentDetailView(generics.GenericAPIView):
    """
    PUT/PATCH /api/comments/<id>/  edit text (author only)
    DELETE    /api/comments/<id>/  delete (author or admin); replies are deleted too
    """

    queryset = Comment.objects.select_related("author", "post")
    permission_classes = [IsAuthenticated, IsCommentOwnerOrAdminCanDelete]

    def _update(self, request, partial: bool) -> Response:
        comment = self.get_object()
        serializer = CommentUpdateSerializer(comment, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CommentSerializer(comment, context={"request": request}).data)

    def put(self, request, pk: int) -> Response:
        return self._update(request, partial=False)

    def patch(self, request, pk: int) -> Response:
        return self._update(request, partial=True)

    def delete(self, request, pk: int) -> Response:
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------- categories & tags
class CategoryListView(generics.ListAPIView):
    """GET /api/categories/ -> categories with number of published posts."""

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends: list = []

    def get_queryset(self):
        return Category.objects.annotate(
            post_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
        ).order_by("name")


class TagListView(generics.ListAPIView):
    """GET /api/tags/ -> tags with number of published posts."""

    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends: list = []

    def get_queryset(self):
        return Tag.objects.annotate(
            post_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
        ).order_by("name")
