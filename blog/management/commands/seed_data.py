"""
Seed the database with demo data.

    python manage.py seed_data            # create data (skips if already seeded)
    python manage.py seed_data --flush    # remove demo data first, then re-create

Creates: 1 admin, 3 users, 4 categories, 8 tags, 15 posts (13 published,
2 drafts), plus comments, replies, likes and bookmarks.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from blog.models import Category, Comment, Post, Tag

User = get_user_model()

ADMIN = {"email": "admin@example.com", "username": "admin", "password": "Admin12345!"}
USERS = [
    {"email": "alice@example.com", "username": "alice", "first_name": "Alice", "last_name": "Johnson",
     "bio": "Backend developer who loves Django and clean APIs."},
    {"email": "bob@example.com", "username": "bob", "first_name": "Bob", "last_name": "Smith",
     "bio": "Full-stack engineer. Coffee, code and React."},
    {"email": "carol@example.com", "username": "carol", "first_name": "Carol", "last_name": "Davis",
     "bio": "Writer and traveller sharing stories from the road."},
]
USER_PASSWORD = "Password123!"

CATEGORIES = [
    ("Technology", "News, trends and ideas from the tech world."),
    ("Programming", "Tutorials and deep-dives for developers."),
    ("Lifestyle", "Productivity, habits and balanced living."),
    ("Travel", "Stories and guides from around the globe."),
]
TAGS = ["Django", "Python", "REST API", "JavaScript", "React", "Web Dev", "Tutorial", "Career"]

# (title, category, tags, author index, status)
POSTS = [
    ("Getting Started with Django REST Framework", "Programming", ["Django", "Python", "REST API", "Tutorial"], 0, "published"),
    ("Why JWT Authentication Is Popular for APIs", "Programming", ["REST API", "Web Dev", "Django"], 0, "published"),
    ("Ten Python Tips I Wish I Knew Earlier", "Programming", ["Python", "Tutorial"], 0, "published"),
    ("Building a React Frontend for Your Django API", "Technology", ["React", "JavaScript", "Django", "Web Dev"], 1, "published"),
    ("Understanding the Django ORM and N+1 Queries", "Programming", ["Django", "Python", "Tutorial"], 0, "published"),
    ("How to Prepare for a Junior Developer Interview", "Lifestyle", ["Career", "Tutorial"], 1, "published"),
    ("JavaScript Async/Await Explained Simply", "Programming", ["JavaScript", "Web Dev", "Tutorial"], 1, "published"),
    ("The Future of Web Development", "Technology", ["Web Dev", "JavaScript", "React"], 1, "published"),
    ("A Week in Lisbon: What to See and Eat", "Travel", [], 2, "published"),
    ("Building Better Habits as a Developer", "Lifestyle", ["Career"], 2, "published"),
    ("Designing Clean REST API Endpoints", "Technology", ["REST API", "Web Dev", "Python"], 0, "published"),
    ("Packing Light: A Minimalist Travel Guide", "Travel", [], 2, "published"),
    ("Testing Django Apps with APITestCase", "Programming", ["Django", "Python", "REST API", "Tutorial"], 0, "published"),
    ("Draft: Notes on Caching Strategies", "Technology", ["Web Dev", "Python"], 0, "draft"),
    ("Draft: My React Learning Roadmap", "Programming", ["React", "JavaScript", "Career"], 1, "draft"),
]

OPENERS = [
    "{topic} is something almost every developer runs into sooner or later, and getting it right pays off quickly.",
    "In this post we take a practical look at {topic}, focusing on what actually matters day to day.",
    "Whether you are just starting out or have years of experience, {topic} is worth a closer look.",
]
PARAGRAPHS = [
    "The best way to learn is to build something small and real. Start with a minimal version, get it working end to end, and only then add features. Every extra layer you add should solve a problem you have actually felt, not one you imagine you might have someday.",
    "Readable code is a gift to your future self. Choose clear names, keep functions short, and write a comment whenever the reason for a decision is not obvious from the code itself. A few minutes of care now saves hours of confusion later.",
    "Testing gives you the confidence to change things. Start with the happy path, then add the awkward cases: empty input, missing permissions and unexpected values. A fast test suite that you trust is one of the most valuable assets a project can have.",
    "Performance problems rarely appear where you expect them. Measure before you optimise, and look at the number of database queries before blaming the language. Fetching related data in one query instead of one hundred is often the biggest win available.",
    "Good documentation is part of the product. A short README that explains how to install, run and test the project removes most of the friction for new contributors, and it often turns out that the new contributor is you six months from now.",
    "Security deserves attention from day one. Never trust user input, keep secrets out of version control, and give every endpoint the smallest set of permissions that still lets it do its job. It is far easier to start strict than to tighten things later.",
    "Take regular breaks and keep learning in small, steady steps. Progress compounds: thirty focused minutes a day beats an exhausting weekend marathon, and you will remember far more of what you read.",
    "Share what you learn. Writing about a topic forces you to understand it properly, and your explanation might be exactly what another beginner needs to finally make it click.",
]
COMMENT_TEXTS = [
    "Great article, thanks for sharing!",
    "This cleared up a lot of confusion for me.",
    "Very helpful, I will try this in my own project.",
    "Nice write-up. Could you cover testing in a follow-up?",
    "I disagree on one point, but overall a solid read.",
    "Bookmarked for later. Exactly what I was looking for.",
]
REPLY_TEXTS = [
    "Glad it helped!",
    "Good idea, I will put that on my list.",
    "Thanks for reading and for the kind words.",
]


class Command(BaseCommand):
    help = "Create demo users, categories, tags, posts, comments, likes and bookmarks."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--flush", action="store_true", help="Delete existing demo data before seeding."
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        if options["flush"]:
            self._flush()
        elif Post.objects.exists() and User.objects.filter(email=ADMIN["email"]).exists():
            self.stdout.write(self.style.WARNING(
                "Data already present. Run with --flush to recreate the demo data."))
            return

        rng = random.Random(42)  # deterministic: same demo data every time
        admin = self._create_admin()
        users = self._create_users()
        categories = self._create_categories()
        tags = self._create_tags()
        posts = self._create_posts(rng, users, categories, tags)
        self._create_comments(rng, posts, users + [admin])
        self._create_likes_and_bookmarks(rng, posts, users + [admin])

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(users) + 1} users, {len(categories)} categories, {len(tags)} tags, "
            f"{len(posts)} posts, {Comment.objects.count()} comments."))
        self.stdout.write("")
        self.stdout.write(f"  Admin login : {ADMIN['email']} / {ADMIN['password']}")
        self.stdout.write(f"  User logins : alice@example.com, bob@example.com, carol@example.com / {USER_PASSWORD}")

    # --------------------------------------------------------------- helpers
    def _flush(self) -> None:
        Comment.objects.all().delete()
        Post.objects.all().delete()
        Tag.objects.all().delete()
        Category.objects.all().delete()
        emails = [ADMIN["email"], *[u["email"] for u in USERS]]
        User.objects.filter(email__in=emails).delete()
        self.stdout.write("Existing demo data removed.")

    def _create_admin(self):
        admin, _ = User.objects.get_or_create(
            email=ADMIN["email"],
            defaults={"username": ADMIN["username"], "is_staff": True, "is_superuser": True,
                      "bio": "Site administrator."},
        )
        admin.set_password(ADMIN["password"])
        admin.is_staff = admin.is_superuser = True
        admin.save()
        return admin

    def _create_users(self) -> list:
        users = []
        for data in USERS:
            data = dict(data)
            email = data.pop("email")
            user, _ = User.objects.get_or_create(email=email, defaults=data)
            user.set_password(USER_PASSWORD)
            user.save()
            users.append(user)
        return users

    def _create_categories(self) -> dict:
        return {
            name: Category.objects.get_or_create(name=name, defaults={"description": desc})[0]
            for name, desc in CATEGORIES
        }

    def _create_tags(self) -> dict:
        return {name: Tag.objects.get_or_create(name=name)[0] for name in TAGS}

    def _create_posts(self, rng, users, categories, tags) -> list:
        now = timezone.now()
        posts = []
        for index, (title, category, tag_names, author_idx, status) in enumerate(POSTS):
            topic = title.replace("Draft: ", "").lower()
            body = [rng.choice(OPENERS).format(topic=topic)]
            body += rng.sample(PARAGRAPHS, k=rng.randint(4, 7))
            post = Post.objects.create(
                title=title,
                author=users[author_idx],
                category=categories[category],
                content="\n\n".join(body),
                status=status,
            )
            post.tags.set([tags[name] for name in tag_names])
            if status == "published":
                # Most posts are recent (so /trending/ has data); a few are older.
                days_ago = rng.uniform(0, 6) if index % 4 else rng.uniform(10, 40)
                Post.objects.filter(pk=post.pk).update(
                    published_at=now - timedelta(days=days_ago),
                    view_count=rng.randint(20, 600),
                )
                post.refresh_from_db()
            posts.append(post)
        return posts

    def _create_comments(self, rng, posts, commenters) -> None:
        for post in (p for p in posts if p.status == "published"):
            for _ in range(rng.randint(1, 3)):
                author = rng.choice(commenters)
                comment = Comment.objects.create(
                    post=post, author=author, content=rng.choice(COMMENT_TEXTS))
                if rng.random() < 0.5:  # roughly half get a reply
                    replier = rng.choice([u for u in commenters if u != author])
                    Comment.objects.create(
                        post=post, author=replier, parent=comment, content=rng.choice(REPLY_TEXTS))

    def _create_likes_and_bookmarks(self, rng, posts, people) -> None:
        for post in (p for p in posts if p.status == "published"):
            post.likes.add(*rng.sample(people, k=rng.randint(0, len(people))))
            post.bookmarks.add(*rng.sample(people, k=rng.randint(0, 2)))
