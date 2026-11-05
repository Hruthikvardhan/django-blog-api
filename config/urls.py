"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts import urls as accounts_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    # /api/auth/register/, login/, token/refresh/, logout/, me/, change-password/
    path("api/auth/", include(accounts_urls.auth_urlpatterns)),
    # /api/users/<username>/
    path("api/users/", include(accounts_urls.user_urlpatterns)),
    # /api/posts/..., /api/comments/..., /api/categories/, /api/tags/
    path("api/", include("blog.urls")),
]

# Serve uploaded media (avatars, featured images) in development only.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
