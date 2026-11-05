"""Serializers for posts, comments, categories and tags."""
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Category, Comment, Post, Tag

User = get_user_model()


# ---------------------------------------------------------------- small pieces
class AuthorSerializer(serializers.ModelSerializer):
    """Minimal public author info embedded in posts and comments."""

    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "name", "avatar")

    def get_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class TagMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class CategorySerializer(serializers.ModelSerializer):
    """Category with number of published posts (annotated in the view)."""

    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "post_count")


class TagSerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "post_count")


# ---------------------------------------------------------------------- posts
class PostListSerializer(serializers.ModelSerializer):
    """Light representation used in lists (no full content)."""

    author = AuthorSerializer(read_only=True)
    category = CategoryMiniSerializer(read_only=True)
    tags = TagMiniSerializer(many=True, read_only=True)
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "slug",
            "excerpt",
            "author",
            "category",
            "tags",
            "featured_image",
            "status",
            "read_time",
            "view_count",
            "like_count",
            "comment_count",
            "is_liked",
            "is_bookmarked",
            "published_at",
            "created_at",
        )

    # The values below are annotated by Post.objects.with_stats(); the fallbacks
    # only run if a plain queryset is serialised (costs extra queries).
    def get_like_count(self, obj) -> int:
        if hasattr(obj, "like_count"):
            return obj.like_count
        return obj.likes.count()

    def get_comment_count(self, obj) -> int:
        if hasattr(obj, "comment_count"):
            return obj.comment_count
        return obj.comments.count()

    def get_is_liked(self, obj) -> bool:
        if hasattr(obj, "is_liked"):
            return bool(obj.is_liked)
        user = self._user()
        return bool(user and obj.likes.filter(pk=user.pk).exists())

    def get_is_bookmarked(self, obj) -> bool:
        if hasattr(obj, "is_bookmarked"):
            return bool(obj.is_bookmarked)
        user = self._user()
        return bool(user and obj.bookmarks.filter(pk=user.pk).exists())

    def _user(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return user if user is not None and user.is_authenticated else None


class PostDetailSerializer(PostListSerializer):
    """Full post including content."""

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ("content", "updated_at")


class PostWriteSerializer(serializers.ModelSerializer):
    """
    Create / update a post.

    * `category` is the category *slug*.
    * `tags` is a list of tag *names*; missing tags are created on the fly.
    """

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Category.objects.all(),
        required=False,
        allow_null=True,
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
    )
    excerpt = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Post
        fields = ("title", "content", "excerpt", "category", "tags", "featured_image", "status")

    @staticmethod
    def _set_tags(post: Post, names: list[str]) -> None:
        """Get or create each tag (case-insensitive) and attach it to the post."""
        tags = []
        for raw in names:
            name = raw.strip()
            if not name:
                continue
            tag = Tag.objects.filter(name__iexact=name).first() or Tag.objects.create(name=name)
            if tag not in tags:
                tags.append(tag)
        post.tags.set(tags)

    @transaction.atomic
    def create(self, validated_data: dict) -> Post:
        tag_names = validated_data.pop("tags", [])
        post = Post.objects.create(**validated_data)
        self._set_tags(post, tag_names)
        return post

    @transaction.atomic
    def update(self, instance: Post, validated_data: dict) -> Post:
        tag_names = validated_data.pop("tags", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tag_names is not None:
            self._set_tags(instance, tag_names)
        return instance


# ------------------------------------------------------------------- comments
class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "author", "content", "parent", "created_at", "updated_at")


class CommentSerializer(serializers.ModelSerializer):
    """A comment with its replies nested. `parent` (optional) makes it a reply."""

    author = AuthorSerializer(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(), required=False, allow_null=True
    )
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("id", "post", "author", "content", "parent", "replies", "created_at", "updated_at")
        read_only_fields = ("post",)

    def get_replies(self, obj) -> list:
        # `obj.replies.all()` hits the prefetch cache when the view prefetched it.
        return ReplySerializer(obj.replies.all(), many=True, context=self.context).data

    def validate_parent(self, parent: Comment | None) -> Comment | None:
        if parent is None:
            return None
        post = self.context["post"]
        if parent.post_id != post.id:
            raise serializers.ValidationError("Parent comment belongs to a different post.")
        if parent.parent_id is not None:
            raise serializers.ValidationError("Replies can only be one level deep.")
        return parent


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Only the text of a comment can be edited."""

    class Meta:
        model = Comment
        fields = ("content",)
