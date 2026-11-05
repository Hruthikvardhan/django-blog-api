"""Django admin configuration for the blog models."""
from django.contrib import admin
from django.db.models import Count

from .models import Category, Comment, Post, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "post_total")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Posts")
    def post_total(self, obj) -> int:
        return obj.posts.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "post_total")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Posts")
    def post_total(self, obj) -> int:
        return obj.posts.count()


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("author", "content", "parent")
    raw_id_fields = ("author", "parent")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title", "author", "category", "status", "view_count", "like_total", "published_at",
    )
    list_filter = ("status", "category", "tags", "created_at", "published_at")
    search_fields = ("title", "content", "author__username", "author__email")
    date_hierarchy = "created_at"
    list_select_related = ("author", "category")
    raw_id_fields = ("author",)
    filter_horizontal = ("tags", "likes", "bookmarks")
    readonly_fields = ("slug", "read_time", "view_count", "created_at", "updated_at")
    inlines = [CommentInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_likes=Count("likes", distinct=True))

    @admin.display(description="Likes", ordering="_likes")
    def like_total(self, obj) -> int:
        return obj._likes


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "short_content", "author", "post", "parent", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content", "author__username", "post__title")
    list_select_related = ("author", "post", "parent")
    raw_id_fields = ("post", "author", "parent")

    @admin.display(description="Content")
    def short_content(self, obj) -> str:
        return obj.content[:60]
