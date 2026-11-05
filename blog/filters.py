"""django-filter FilterSet for GET /api/posts/."""
import django_filters
from django.db.models import Q

from .models import Post


class PostFilter(django_filters.FilterSet):
    """
    ?search=django   title, content or tag name contains the text
    ?category=slug   category slug
    ?tag=slug        tag slug
    ?author=username author username
    """

    search = django_filters.CharFilter(method="filter_search")
    category = django_filters.CharFilter(field_name="category__slug")
    tag = django_filters.CharFilter(field_name="tags__slug")
    author = django_filters.CharFilter(field_name="author__username")

    class Meta:
        model = Post
        fields: list[str] = []

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value)
            | Q(content__icontains=value)
            | Q(tags__name__icontains=value)
        ).distinct()
