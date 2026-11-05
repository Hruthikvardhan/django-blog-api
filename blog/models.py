"""Blog models: Category, Tag, Post, Comment."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import BooleanField, Count, Exists, OuterRef, Value
from django.utils import timezone

from .utils import calculate_read_time, generate_unique_slug, make_excerpt


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = generate_unique_slug(Category, self.name, self.pk, 120)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = generate_unique_slug(Tag, self.name, self.pk, 70)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class PostQuerySet(models.QuerySet):
    """Reusable query helpers that also prevent N+1 queries."""

    def published(self) -> "PostQuerySet":
        return self.filter(status=Post.Status.PUBLISHED)

    def with_stats(self, user=None) -> "PostQuerySet":
        """
        Join related rows and annotate counts in ONE query:
        like_count, comment_count, is_liked, is_bookmarked.
        """
        qs = (
            self.select_related("author", "category")
            .prefetch_related("tags")
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
            )
        )
        if user is not None and user.is_authenticated:
            qs = qs.annotate(
                is_liked=Exists(
                    Post.likes.through.objects.filter(post_id=OuterRef("pk"), user_id=user.pk)
                ),
                is_bookmarked=Exists(
                    Post.bookmarks.through.objects.filter(post_id=OuterRef("pk"), user_id=user.pk)
                ),
            )
        else:
            qs = qs.annotate(
                is_liked=Value(False, output_field=BooleanField()),
                is_bookmarked=Value(False, output_field=BooleanField()),
            )
        return qs


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    content = models.TextField()
    excerpt = models.TextField(blank=True, help_text="Auto-generated from content if left empty.")
    featured_image = models.ImageField(upload_to="posts/", blank=True, null=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    view_count = models.PositiveIntegerField(default=0)
    read_time = models.PositiveIntegerField(default=1, help_text="Minutes (200 words/min).")
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="liked_posts"
    )
    bookmarks = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="bookmarked_posts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
        ]

    def save(self, *args, **kwargs) -> None:
        # Unique slug is generated once, so URLs stay stable when the title changes.
        if not self.slug:
            self.slug = generate_unique_slug(Post, self.title, self.pk, 255, fallback="post")
        if not self.excerpt:
            self.excerpt = make_excerpt(self.content)
        self.read_time = calculate_read_time(self.content)
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def clean(self) -> None:
        """Only one level of replies: a reply cannot itself be replied to."""
        if self.parent_id:
            if self.parent.parent_id is not None:
                raise ValidationError("Replies can only be one level deep.")
            if self.parent.post_id != self.post_id:
                raise ValidationError("Parent comment belongs to a different post.")

    def __str__(self) -> str:
        return f"Comment #{self.pk} by {self.author} on {self.post}"
