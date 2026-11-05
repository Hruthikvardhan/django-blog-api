"""Tests for posts, permissions, likes, bookmarks, comments, search and pagination."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Comment, Post, Tag
from .utils import calculate_read_time, make_excerpt

User = get_user_model()


class BlogTestCase(APITestCase):
    """Shared fixtures: two users, an admin, a category and helpers."""

    def setUp(self) -> None:
        self.alice = User.objects.create_user("alice", "alice@example.com", "StrongPass123!")
        self.bob = User.objects.create_user("bob", "bob@example.com", "StrongPass123!")
        self.admin = User.objects.create_superuser("root", "root@example.com", "StrongPass123!")
        self.category = Category.objects.create(name="Programming")

    def make_post(self, author=None, title="Hello World", status_="published", **extra) -> Post:
        return Post.objects.create(
            title=title,
            author=author or self.alice,
            content=extra.pop("content", "Some content about Django. " * 5),
            status=status_,
            **extra,
        )

    def detail_url(self, post: Post) -> str:
        return reverse("post-detail", kwargs={"slug": post.slug})


class PostCrudTests(BlogTestCase):
    def test_create_post_requires_login(self) -> None:
        res = self.client.post(reverse("post-list"), {"title": "x", "content": "y"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_post_with_category_slug_and_new_tags(self) -> None:
        self.client.force_authenticate(self.alice)
        res = self.client.post(
            reverse("post-list"),
            {
                "title": "My First Post",
                "content": "word " * 450,
                "category": self.category.slug,
                "tags": ["Django", "New Tag"],
                "status": "published",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["slug"], "my-first-post")
        self.assertEqual(res.data["author"]["username"], "alice")
        self.assertEqual(res.data["category"]["slug"], "programming")
        self.assertEqual({t["name"] for t in res.data["tags"]}, {"Django", "New Tag"})
        self.assertEqual(res.data["read_time"], 3)  # 450 words / 200 = 2.25 -> 3 min
        self.assertTrue(res.data["excerpt"])
        self.assertIsNotNone(res.data["published_at"])
        self.assertTrue(Tag.objects.filter(name="New Tag").exists())

    def test_duplicate_title_gets_unique_slug(self) -> None:
        first = self.make_post(title="Same Title")
        second = self.make_post(title="Same Title")
        self.assertEqual(first.slug, "same-title")
        self.assertNotEqual(second.slug, first.slug)
        self.assertTrue(second.slug.startswith("same-title-"))

    def test_non_author_cannot_update_or_delete(self) -> None:
        post = self.make_post(author=self.alice)
        self.client.force_authenticate(self.bob)

        res = self.client.put(self.detail_url(post), {"title": "Hacked", "content": "x"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("detail", res.data)

        res = self.client.delete(self.detail_url(post))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())

    def test_author_can_update_and_delete(self) -> None:
        post = self.make_post(author=self.alice)
        self.client.force_authenticate(self.alice)

        res = self.client.put(
            self.detail_url(post),
            {"title": "Updated Title", "content": "Brand new content here."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["title"], "Updated Title")
        self.assertEqual(res.data["slug"], post.slug)  # slug stays stable

        res = self.client.delete(self.detail_url(post))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_detail_increments_view_count(self) -> None:
        post = self.make_post()
        self.client.get(self.detail_url(post))
        res = self.client.get(self.detail_url(post))
        self.assertEqual(res.data["view_count"], 2)
        post.refresh_from_db()
        self.assertEqual(post.view_count, 2)

    def test_drafts_visible_only_to_author(self) -> None:
        draft = self.make_post(title="Secret Draft", status_="draft")

        # Not in the public list, and detail is 404 for anonymous and other users.
        self.assertEqual(self.client.get(reverse("post-list")).data["count"], 0)
        self.assertEqual(self.client.get(self.detail_url(draft)).status_code, 404)
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get(self.detail_url(draft)).status_code, 404)

        # The author can open it and sees it under /my/.
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.get(self.detail_url(draft)).status_code, 200)
        res = self.client.get(reverse("post-my"))
        self.assertEqual([p["title"] for p in res.data["results"]], ["Secret Draft"])

    def test_my_posts_only_contains_own_posts(self) -> None:
        self.make_post(author=self.alice, title="Alice published")
        self.make_post(author=self.alice, title="Alice draft", status_="draft")
        self.make_post(author=self.bob, title="Bob post")
        self.client.force_authenticate(self.alice)
        res = self.client.get(reverse("post-my"))
        self.assertEqual(res.data["count"], 2)

    def test_publishing_sets_published_at(self) -> None:
        draft = self.make_post(status_="draft")
        self.assertIsNone(draft.published_at)
        draft.status = Post.Status.PUBLISHED
        draft.save()
        self.assertIsNotNone(draft.published_at)


class InteractionTests(BlogTestCase):
    def test_like_toggle(self) -> None:
        post = self.make_post()
        url = reverse("post-like", kwargs={"slug": post.slug})
        self.client.force_authenticate(self.bob)

        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"liked": True, "like_count": 1})

        res = self.client.post(url)
        self.assertEqual(res.data, {"liked": False, "like_count": 0})

    def test_like_requires_login(self) -> None:
        post = self.make_post()
        res = self.client.post(reverse("post-like", kwargs={"slug": post.slug}))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bookmark_toggle_and_list(self) -> None:
        post = self.make_post()
        self.client.force_authenticate(self.bob)
        url = reverse("post-bookmark", kwargs={"slug": post.slug})

        self.assertTrue(self.client.post(url).data["bookmarked"])
        res = self.client.get(reverse("post-bookmarks"))
        self.assertEqual(res.data["count"], 1)
        self.assertTrue(res.data["results"][0]["is_bookmarked"])

        self.assertFalse(self.client.post(url).data["bookmarked"])
        self.assertEqual(self.client.get(reverse("post-bookmarks")).data["count"], 0)

    def test_list_flags_reflect_current_user(self) -> None:
        post = self.make_post()
        post.likes.add(self.bob)
        self.client.force_authenticate(self.bob)
        item = self.client.get(reverse("post-list")).data["results"][0]
        self.assertTrue(item["is_liked"])
        self.assertFalse(item["is_bookmarked"])
        self.assertEqual(item["like_count"], 1)

        self.client.force_authenticate(None)
        item = self.client.get(reverse("post-list")).data["results"][0]
        self.assertFalse(item["is_liked"])

    def test_trending_ranks_by_views_plus_likes_in_last_7_days(self) -> None:
        popular = self.make_post(title="Popular", view_count=50)
        quiet = self.make_post(title="Quiet", view_count=1)
        old = self.make_post(title="Old but huge", view_count=9999)
        Post.objects.filter(pk=old.pk).update(published_at=timezone.now() - timedelta(days=30))
        popular.likes.add(self.alice, self.bob)

        res = self.client.get(reverse("post-trending"))
        self.assertEqual(res.status_code, 200)
        titles = [p["title"] for p in res.data]
        self.assertEqual(titles, ["Popular", "Quiet"])  # old post excluded


class CommentTests(BlogTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.post = self.make_post()
        self.url = reverse("post-comments", kwargs={"slug": self.post.slug})

    def test_anonymous_cannot_comment_but_can_read(self) -> None:
        res = self.client.post(self.url, {"content": "hi"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_comment_and_reply_are_nested(self) -> None:
        self.client.force_authenticate(self.bob)
        parent = self.client.post(self.url, {"content": "Nice post"})
        self.assertEqual(parent.status_code, 201, parent.data)

        self.client.force_authenticate(self.alice)
        reply = self.client.post(self.url, {"content": "Thanks!", "parent": parent.data["id"]})
        self.assertEqual(reply.status_code, 201, reply.data)

        res = self.client.get(self.url)
        self.assertEqual(len(res.data), 1)  # only top-level comments are listed
        self.assertEqual(res.data[0]["content"], "Nice post")
        self.assertEqual(len(res.data[0]["replies"]), 1)
        self.assertEqual(res.data[0]["replies"][0]["author"]["username"], "alice")

    def test_reply_to_reply_is_rejected(self) -> None:
        parent = Comment.objects.create(post=self.post, author=self.bob, content="top")
        reply = Comment.objects.create(post=self.post, author=self.alice, content="r", parent=parent)
        self.client.force_authenticate(self.bob)
        res = self.client.post(self.url, {"content": "too deep", "parent": reply.pk})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_author_can_edit_comment(self) -> None:
        comment = Comment.objects.create(post=self.post, author=self.bob, content="original")
        url = reverse("comment-detail", kwargs={"pk": comment.pk})

        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.put(url, {"content": "hacked"}).status_code, 403)

        self.client.force_authenticate(self.bob)
        res = self.client.put(url, {"content": "edited"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["content"], "edited")

    def test_delete_comment_author_admin_only(self) -> None:
        comment = Comment.objects.create(post=self.post, author=self.bob, content="bye")
        url = reverse("comment-detail", kwargs={"pk": comment.pk})

        self.client.force_authenticate(self.alice)  # random user
        self.assertEqual(self.client.delete(url).status_code, 403)

        self.client.force_authenticate(self.admin)  # admin may delete
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

        own = Comment.objects.create(post=self.post, author=self.bob, content="mine")
        self.client.force_authenticate(self.bob)  # author may delete
        res = self.client.delete(reverse("comment-detail", kwargs={"pk": own.pk}))
        self.assertEqual(res.status_code, 204)


class SearchFilterPaginationTests(BlogTestCase):
    def test_search_matches_title_content_and_tags(self) -> None:
        by_title = self.make_post(title="Learning Django")
        by_content = self.make_post(title="Other", content="This is about django internals.")
        by_tag = self.make_post(title="Unrelated")
        by_tag.tags.add(Tag.objects.create(name="Django Tips"))
        self.make_post(title="Cooking pasta", content="Boil water.")

        res = self.client.get(reverse("post-list"), {"search": "django"})
        self.assertEqual(res.data["count"], 3)
        titles = {p["title"] for p in res.data["results"]}
        self.assertEqual(titles, {by_title.title, by_content.title, by_tag.title})

    def test_filter_by_category_tag_and_author(self) -> None:
        tag = Tag.objects.create(name="Python")
        a = self.make_post(author=self.alice, title="A", category=self.category)
        a.tags.add(tag)
        self.make_post(author=self.bob, title="B")

        self.assertEqual(self.client.get(reverse("post-list"), {"category": "programming"}).data["count"], 1)
        self.assertEqual(self.client.get(reverse("post-list"), {"tag": "python"}).data["count"], 1)
        res = self.client.get(reverse("post-list"), {"author": "bob"})
        self.assertEqual([p["title"] for p in res.data["results"]], ["B"])

    def test_ordering_by_view_count(self) -> None:
        self.make_post(title="Low", view_count=1)
        self.make_post(title="High", view_count=99)
        res = self.client.get(reverse("post-list"), {"ordering": "-view_count"})
        self.assertEqual([p["title"] for p in res.data["results"]], ["High", "Low"])

    def test_pagination_is_ten_per_page(self) -> None:
        for i in range(15):
            self.make_post(title=f"Post {i}")
        page1 = self.client.get(reverse("post-list"))
        self.assertEqual(page1.data["count"], 15)
        self.assertEqual(len(page1.data["results"]), 10)
        self.assertIsNotNone(page1.data["next"])

        page2 = self.client.get(reverse("post-list"), {"page": 2})
        self.assertEqual(len(page2.data["results"]), 5)

    def test_list_query_count_does_not_grow_with_posts(self) -> None:
        """select_related / prefetch_related keep the list at a constant number of queries."""
        for i in range(3):
            self.make_post(title=f"Few {i}").tags.add(Tag.objects.create(name=f"t{i}"))
        with self.assertNumQueries(3):  # count + posts + tags prefetch
            self.client.get(reverse("post-list"))

        for i in range(7):
            self.make_post(title=f"Many {i}").tags.add(Tag.objects.create(name=f"m{i}"))
        with self.assertNumQueries(3):
            self.client.get(reverse("post-list"))


class MetaEndpointTests(BlogTestCase):
    def test_categories_and_tags_have_published_post_counts(self) -> None:
        tag = Tag.objects.create(name="Python")
        published = self.make_post(category=self.category)
        published.tags.add(tag)
        draft = self.make_post(title="Draft", status_="draft", category=self.category)
        draft.tags.add(tag)

        cats = self.client.get(reverse("category-list")).data
        self.assertEqual(cats[0]["name"], "Programming")
        self.assertEqual(cats[0]["post_count"], 1)  # draft not counted

        tags = self.client.get(reverse("tag-list")).data
        self.assertEqual(tags[0]["post_count"], 1)

    def test_public_profile_shows_published_posts_only(self) -> None:
        self.make_post(author=self.alice, title="Public one")
        self.make_post(author=self.alice, title="Hidden draft", status_="draft")
        res = self.client.get(reverse("public-profile", kwargs={"username": "alice"}))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "alice")
        self.assertNotIn("email", res.data)
        self.assertEqual(res.data["post_count"], 1)
        self.assertEqual(res.data["posts"]["count"], 1)

    def test_unknown_profile_returns_404_json(self) -> None:
        res = self.client.get(reverse("public-profile", kwargs={"username": "ghost"}))
        self.assertEqual(res.status_code, 404)
        self.assertIn("detail", res.data)


class UtilsTests(APITestCase):
    def test_read_time_uses_200_words_per_minute(self) -> None:
        self.assertEqual(calculate_read_time(""), 1)
        self.assertEqual(calculate_read_time("word " * 200), 1)
        self.assertEqual(calculate_read_time("word " * 201), 2)

    def test_excerpt_is_truncated_at_word_boundary(self) -> None:
        text = "alpha beta gamma " * 40
        excerpt = make_excerpt(text, length=50)
        self.assertTrue(excerpt.endswith("..."))
        self.assertLessEqual(len(excerpt), 53)
        self.assertEqual(make_excerpt("short text"), "short text")
