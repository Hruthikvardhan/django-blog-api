# Blog Platform REST API

A complete blog backend built with **Django 5 + Django REST Framework**, JWT authentication
(SimpleJWT with refresh rotation and blacklist), SQLite, filtering, search, pagination,
admin, seed data and 40 automated tests. No Docker, Redis, Celery or PostgreSQL needed.

```
blog_project/
  config/      settings.py  urls.py  wsgi.py  exceptions.py (uniform {"detail": ...} errors)
  accounts/    User model, register/login/logout/profile/password endpoints
  blog/        Category, Tag, Post, Comment, likes, bookmarks, filters, seed command
  manage.py  requirements.txt  .env.example  .gitignore
```

---

## 1. Run it on Windows (step by step)

Open **Command Prompt** (or PowerShell) and go to the project folder.

```bat
cd path\to\blog_project

:: 1. Create and activate a virtual environment (Python 3.10+)
python -m venv venv
venv\Scripts\activate

:: 2. Install dependencies
pip install -r requirements.txt

:: 3. Create your .env file
copy .env.example .env

:: 4. Create the database tables
python manage.py migrate

:: 5. (Optional but recommended) load demo data
python manage.py seed_data

:: 6. Start the server  ->  http://127.0.0.1:8000/
python manage.py runserver
```

PowerShell users: if `venv\Scripts\activate` is blocked, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first.

Other commands:

```bat
python manage.py test                 :: run all 40 tests
python manage.py createsuperuser      :: asks for email, username, password
python manage.py seed_data --flush    :: wipe demo data and re-create it
```

**Demo logins created by `seed_data`**

| Role  | Email               | Password       |
|-------|---------------------|----------------|
| Admin | admin@example.com   | `Admin12345!`  |
| User  | alice@example.com   | `Password123!` |
| User  | bob@example.com     | `Password123!` |
| User  | carol@example.com   | `Password123!` |

Django admin: http://127.0.0.1:8000/admin/ (log in with the **email**).

---

## 2. Endpoint examples (curl / Postman)

Base URL: `http://127.0.0.1:8000/api`. In **Postman**, create an environment variable `token`,
and on protected requests choose *Authorization -> Bearer Token -> `{{token}}`*.

> **Windows note:** `cmd.exe` handles quotes differently from bash. The examples below use
> bash-style quoting (works in **Git Bash**, macOS, Linux, WSL). In cmd/PowerShell it is easiest
> to use Postman, or use `curl.exe` and escape the inner quotes (`-d "{\"email\":\"a@b.com\"}"`).

Replace `$TOKEN` with the `access` value from login and `$REFRESH` with the `refresh` value.

### Auth

```bash
# Register -> 201 {"user": {...}, "tokens": {"access", "refresh"}}
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"new@example.com","username":"newuser","password":"StrongPass123!"}'

# Login -> {"access", "refresh", "user"}
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"Password123!"}'

# Refresh (rotation: you get a NEW refresh token; the old one is blacklisted)
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"'$REFRESH'"}'

# Logout (blacklists the refresh token)
curl -X POST http://127.0.0.1:8000/api/auth/logout/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"refresh":"'$REFRESH'"}'

# My profile
curl http://127.0.0.1:8000/api/auth/me/ -H "Authorization: Bearer $TOKEN"

# Update profile (JSON)
curl -X PUT http://127.0.0.1:8000/api/auth/me/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","bio":"Django dev","website":"https://alice.dev"}'

# Update profile with avatar (multipart; in Postman: Body -> form-data, key "avatar" type File)
curl -X PUT http://127.0.0.1:8000/api/auth/me/ \
  -H "Authorization: Bearer $TOKEN" -F "bio=With avatar" -F "avatar=@photo.jpg"

# Change password
curl -X PUT http://127.0.0.1:8000/api/auth/change-password/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"old_password":"Password123!","new_password":"EvenBetterPass456!"}'
```

### Posts

```bash
# List published posts (10 per page)
curl "http://127.0.0.1:8000/api/posts/"

# Search / filter / order / page (combine freely)
curl "http://127.0.0.1:8000/api/posts/?search=django"
curl "http://127.0.0.1:8000/api/posts/?category=programming&tag=django&author=alice"
curl "http://127.0.0.1:8000/api/posts/?ordering=-view_count&page=2"

# Create (login required). category = slug, tags = names (created if new)
curl -X POST http://127.0.0.1:8000/api/posts/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"My Post","content":"Hello world, this is my post.","category":"technology","tags":["Django","My New Tag"],"status":"published"}'

# Create with a featured image (multipart)
curl -X POST http://127.0.0.1:8000/api/posts/ -H "Authorization: Bearer $TOKEN" \
  -F "title=With image" -F "content=Body text" -F "status=draft" \
  -F "tags=django" -F "tags=python" -F "featured_image=@cover.jpg"

# Detail (increments view_count)
curl http://127.0.0.1:8000/api/posts/my-post/

# Update / delete (author only; others get 403)
curl -X PUT http://127.0.0.1:8000/api/posts/my-post/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"My Post (edited)","content":"New content.","status":"published"}'
curl -X DELETE http://127.0.0.1:8000/api/posts/my-post/ -H "Authorization: Bearer $TOKEN"

# My posts (drafts included) and my bookmarks
curl http://127.0.0.1:8000/api/posts/my/ -H "Authorization: Bearer $TOKEN"
curl http://127.0.0.1:8000/api/posts/bookmarks/ -H "Authorization: Bearer $TOKEN"

# Toggle like / bookmark -> {"liked": true, "like_count": 3}
curl -X POST http://127.0.0.1:8000/api/posts/my-post/like/ -H "Authorization: Bearer $TOKEN"
curl -X POST http://127.0.0.1:8000/api/posts/my-post/bookmark/ -H "Authorization: Bearer $TOKEN"

# Trending: top 10 of posts published in the last 7 days, ranked by views + likes
curl http://127.0.0.1:8000/api/posts/trending/
```

### Comments

```bash
# List top-level comments with nested replies
curl http://127.0.0.1:8000/api/posts/my-post/comments/

# Add a comment
curl -X POST http://127.0.0.1:8000/api/posts/my-post/comments/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"Great post!"}'

# Reply (one level only): pass the parent comment id
curl -X POST http://127.0.0.1:8000/api/posts/my-post/comments/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"Thanks!","parent":1}'

# Edit (author only) / delete (author or admin)
curl -X PUT http://127.0.0.1:8000/api/comments/1/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"Edited text"}'
curl -X DELETE http://127.0.0.1:8000/api/comments/1/ -H "Authorization: Bearer $TOKEN"
```

### Other

```bash
curl http://127.0.0.1:8000/api/categories/      # [{"name", "slug", "post_count", ...}]
curl http://127.0.0.1:8000/api/tags/
curl http://127.0.0.1:8000/api/users/alice/     # public profile + paginated published posts
```

### Response shapes

* **Errors** are always `{"detail": "message"}`. Validation errors also include an `errors`
  object with per-field messages: `{"detail": "email: A user with this email already exists.", "errors": {"email": ["..."]}}`
* **Paginated lists** return `{"count", "next", "previous", "results": [...]}`.
* **Status codes:** `401` not logged in, `403` logged in but not allowed, `404` not found
  (also used for other people's drafts), `400` invalid input.

---

## 3. Common errors and fixes

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Reinstall Python from python.org and tick **Add Python to PATH**, or use `py -m venv venv`. |
| `ModuleNotFoundError: No module named 'rest_framework'` | The virtualenv is not active, or deps are missing. Run `venv\Scripts\activate` then `pip install -r requirements.txt`. |
| `no such table: accounts_user` / `no such table: ...` | Run `python manage.py migrate`. |
| `Authentication credentials were not provided` (401) | Add the header `Authorization: Bearer <access token>` (note the word **Bearer** and the space). |
| `Given token not valid for any token type` / `token_not_valid` | Access token expired (60 min). Call `/api/auth/token/refresh/`, or log in again. |
| Login says `No active account found` | Use **email** (not username) in the login body: `{"email": "...", "password": "..."}`. |
| `UNIQUE constraint failed: accounts_user.email` | That email is registered already. |
| `CommandError: ... Pillow` / `ImageField` error | `pip install Pillow` (it is in requirements.txt). |
| Refresh token rejected after use | Expected: rotation blacklists the old refresh token. Always store the **new** one returned by `/token/refresh/`. |
| `Method "POST" not allowed` on `/api/posts/my-post/` | Use the right URL: like/bookmark are `POST /api/posts/<slug>/like/` (trailing slash required). |
| `UnicodeDecodeError` / odd characters in `.env` | Save `.env` as UTF-8 without BOM. |
| Port 8000 busy | `python manage.py runserver 8001`. |
| Postman multipart upload not working | Body -> **form-data** (not raw JSON), set the key type to **File**, do not set Content-Type manually. |
| Browser (React) shows a CORS error | Your dev server must be `http://localhost:5173` or `:3000`; add other origins to `CORS_ALLOWED_ORIGINS` in `settings.py` and restart. |

---

## 4. Django concepts this project teaches

* **Project vs apps**, `INSTALLED_APPS`, settings from environment variables (python-dotenv).
* **Custom user model** (`AbstractUser`, `USERNAME_FIELD = "email"`, `AUTH_USER_MODEL`) and why to
  set it before the first migration.
* **Models & relations:** `ForeignKey`, `ManyToManyField`, self-referencing FK (replies),
  `related_name`, `TextChoices`, `unique`, `Meta.ordering`, `indexes`, overriding `save()`.
* **Custom QuerySet / manager** (`Post.objects.with_stats(user)`).
* **ORM performance:** `select_related`, `prefetch_related`, `annotate` with `Count(distinct=True)`,
  `Exists`/`OuterRef`, `F()` for atomic counters, and `assertNumQueries` to prove no N+1.
* **Migrations:** `makemigrations`, `migrate`.
* **DRF serializers:** `ModelSerializer`, nested serializers, `SerializerMethodField`,
  `SlugRelatedField`, `ListField`, `validate_<field>`, overriding `create`/`update`,
  serializer context, separate read vs write serializers.
* **Views:** `ModelViewSet`, `@action`, `ListCreateAPIView`, `GenericAPIView`, `get_queryset` per
  action, `get_permissions` per action, routers.
* **Authentication & permissions:** JWT access/refresh, rotation, blacklist, `IsAuthenticated`,
  custom object permissions (`IsAuthorOrReadOnly`).
* **Filtering/search/ordering/pagination:** `django-filter`, `OrderingFilter`, `PageNumberPagination`.
* **File uploads:** `ImageField`, `MEDIA_ROOT`, multipart parsers.
* **Error handling:** custom exception handler for a consistent error format.
* **Admin customisation:** `list_display`, `list_filter`, `search_fields`, inlines, `filter_horizontal`.
* **Management commands:** `seed_data` with `--flush`.
* **Testing:** `APITestCase`, `force_authenticate`, `reverse`, permission and query-count tests.
* **CORS** and how a separate frontend talks to an API.

---

## 5. What to say about it in interviews

**30-second pitch**

> "I built a blog platform REST API with Django and Django REST Framework. It has JWT
> authentication with refresh-token rotation and a blacklist, a custom email-based user model,
> posts with categories, tags, likes, bookmarks and threaded comments, plus search, filtering,
> ordering and pagination. I focused on correctness and performance: object-level permissions so
> only authors can edit their posts, annotated querysets so list endpoints run a constant number
> of queries, atomic view counters, and 40 automated tests including a query-count test."

**Design decisions you can defend**

* *Why JWT?* Stateless, works naturally with a separate React/mobile client. Short-lived access
  tokens (60 min) limit exposure; rotating refresh tokens plus a blacklist make logout real.
* *Why a custom user model from day one?* Email login and profile fields; changing it later means
  painful migrations.
* *How did you avoid N+1 queries?* `select_related` for author/category, `prefetch_related` for
  tags and replies, and `annotate` for like/comment counts and `is_liked`/`is_bookmarked`
  (`Exists` subqueries). A test asserts the list endpoint always uses 3 queries.
* *How is the view counter safe under concurrency?* `F("view_count") + 1` is executed by the
  database in a single `UPDATE`, so simultaneous requests don't overwrite each other.
* *Slugs:* generated once from the title (stable URLs), with a random suffix on collision.
* *Security:* drafts return 404 to non-authors (don't leak existence), 403 for forbidden edits,
  private fields (email) are not in public profiles, secrets come from `.env`.
* *Known limitations (shows maturity):* SQLite is for development; no rate limiting; access tokens
  stay valid until they expire after a password change; media is stored on local disk. The
  production path is PostgreSQL, S3-style storage, throttling and a real SECRET_KEY/`DEBUG=False`.

---

## 6. Common Django / DRF interview questions this covers

1. What is the difference between a **project** and an **app**?
2. How does the **request/response cycle** work (URL conf -> view -> serializer -> model)?
3. What are **migrations** and what do `makemigrations` and `migrate` do?
4. Why and how do you create a **custom user model**?
5. `ForeignKey` vs `OneToOneField` vs `ManyToManyField`; what is `related_name`?
6. What is the **N+1 query problem**? `select_related` vs `prefetch_related`?
7. What are `annotate` and `aggregate`? What is `F()` and why use it for counters?
8. What is a **QuerySet**, and why is it lazy?
9. `Serializer` vs `ModelSerializer`; how do you add custom validation?
10. `APIView` vs `GenericAPIView` vs `ViewSet`; when use a `Router`?
11. How do **permissions** work? Difference between `has_permission` and `has_object_permission`?
12. **401 vs 403** and why a draft returns **404**.
13. How does **JWT** work? What are access vs refresh tokens, rotation and blacklisting?
14. How do you implement **pagination, filtering and search** in DRF?
15. How do you handle **file uploads** (`ImageField`, `MEDIA_ROOT`, multipart)?
16. What is **CORS** and how does `django-cors-headers` solve it?
17. What are **signals/management commands**, and when use a command (`seed_data`)?
18. How do you **test** a Django API? (`APITestCase`, `force_authenticate`, test DB.)
19. What does `DEBUG=True` do and why must it be off in production?
20. How would you **deploy** this (gunicorn, PostgreSQL, env vars, static/media storage)?

---

## 7. Connecting a React + Vite frontend later

CORS already allows `http://localhost:5173` (Vite) and `http://localhost:3000`.

**Create the app**

```bash
npm create vite@latest blog-frontend -- --template react
cd blog-frontend
npm install axios react-router-dom
```

**`.env` in the frontend** (Vite only exposes variables starting with `VITE_`):

```
VITE_API_URL=http://127.0.0.1:8000/api
```

**`src/api.js`**: an Axios client that attaches the token and refreshes it automatically:

```js
import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, try once to get a new access token with the refresh token
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const refresh = localStorage.getItem("refresh");
    if (error.response?.status === 401 && refresh && !original._retry) {
      original._retry = true;
      try {
        const { data } = await axios.post(
          `${import.meta.env.VITE_API_URL}/auth/token/refresh/`,
          { refresh }
        );
        localStorage.setItem("access", data.access);
        localStorage.setItem("refresh", data.refresh); // rotation: store the NEW one
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        localStorage.clear(); // refresh failed -> send user to login
      }
    }
    return Promise.reject(error);
  }
);

export default api;
```

**Login and fetching posts**

```js
import api from "./api";

export async function login(email, password) {
  const { data } = await api.post("/auth/login/", { email, password });
  localStorage.setItem("access", data.access);
  localStorage.setItem("refresh", data.refresh);
  return data.user;
}

export const getPosts = (params) => api.get("/posts/", { params }).then((r) => r.data);
// getPosts({ search: "django", page: 2, ordering: "-view_count" })

export const toggleLike = (slug) => api.post(`/posts/${slug}/like/`).then((r) => r.data);
```

**Tips**

* Run both servers: Django on `:8000`, Vite on `:5173`.
* Image fields come back as absolute URLs (e.g. `http://127.0.0.1:8000/media/avatars/x.jpg`).
* Send uploads as `FormData` (`api.put("/auth/me/", formData)`); Axios sets the multipart header.
* Show validation errors from `error.response.data.errors` (per field) or `.detail` (single message).
* `localStorage` is fine for learning; for production consider httpOnly cookies and CSRF protection.
* When you deploy, add your real frontend origin to `CORS_ALLOWED_ORIGINS` and set `DEBUG=False`.
