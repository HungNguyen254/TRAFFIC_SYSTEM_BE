# Auth & Segment CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement User Authentication with JWT Bearer tokens and Role-Based Access Control (RBAC) separating `ADMIN` and `USER` roles, providing full road Segment CRUD for Admins and read-only viewing for regular Users.

**Architecture:** A `User` SQLModel table with `role` enum (`ADMIN`, `USER`) is managed via Alembic migrations. Security utilities (`app/core/security.py`) use standard-library `hashlib.pbkdf2_hmac` for password hashing and `PyJWT` for HS256 tokens. FastAPI dependencies (`app/core/auth.py`) provide `get_current_user` (authenticating tokens) and `require_admin` (authorizing admin role). Auth endpoints (`/api/auth`) handle registration, login (supporting both JSON and Swagger form data), and user profile. `app/api/segments.py` is upgraded to full CRUD (`POST`, `PUT`, `DELETE` requiring Admin; `GET` requiring authenticated User/Admin).

**Tech Stack:** Python 3.14+, FastAPI, SQLModel, PyJWT, Alembic, Pytest.

**Spec:** [`docs/superpowers/specs/2026-11-05-auth-and-segment-crud-design.md`](file:///home/PageNguyen/Projects/TRAFFIC_SYSTEM_BE/docs/superpowers/specs/2026-11-05-auth-and-segment-crud-design.md)

## Global Constraints

- NEVER commit or push (per project forbidden actions).
- NEVER delete files or run destructive terminal commands without asking first.
- NEVER modify anything outside the repository directory (`/home/PageNguyen/Projects/TRAFFIC_SYSTEM_BE`).
- Only add allowed dependency: `pyjwt`. Pin exact tested version in `requirements.txt`.
- Password hashing must use Python's built-in `hashlib.pbkdf2_hmac` with random salt (compatible with Python 3.14, no deprecated `passlib`).
- Database queries and migrations must remain strictly portable across SQLite and PostgreSQL.
- Keep `README.md` <= 10 lines.

## Review Focus

1. **Privilege Escalation via Registration**: Clients calling `POST /api/auth/register` must never be able to assign themselves the `ADMIN` role. Role must always be forced to `USER`.
2. **Unauthorized Access (401)**: Unauthenticated requests (missing, invalid, or expired Bearer token) to protected segment endpoints must be rejected with HTTP 401 Unauthorized.
3. **Forbidden Modification by Regular User (403)**: Authenticated users with role `USER` attempting `POST /api/segments`, `PUT /api/segments/{id}`, or `DELETE /api/segments/{id}` must be rejected with HTTP 403 Forbidden.
4. **Foreign Key Integrity on Segment Deletion**: Deleting a segment (`DELETE /api/segments/{id}`) must clean up associated `TrafficObservation` records first to prevent foreign key constraint violations.
5. **Dual Login Format Support**: `POST /api/auth/login` must accept both JSON (`application/json`) for frontend SPAs and form-data (`application/x-www-form-urlencoded`) for Swagger UI.

---

### Task 1: Dependency Installation & Security Configuration

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/config.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `pyjwt` installed and pinned in `requirements.txt`. `settings.JWT_SECRET_KEY` and `settings.ACCESS_TOKEN_EXPIRE_MINUTES` available in `Settings`.

- [ ] **Step 1: Install `pyjwt` into the virtual environment**
  Run: `uv pip install pyjwt`
- [ ] **Step 2: Check exact installed version of `pyjwt`**
  Run: `uv pip list | grep -E "^pyjwt "`
- [ ] **Step 3: Update `requirements.txt` with pinned `pyjwt`**
  Append exact version (e.g. `pyjwt==2.10.1`) to `requirements.txt`.
- [ ] **Step 4: Update `app/core/config.py`**
  Add `JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"` and `ACCESS_TOKEN_EXPIRE_MINUTES: int = 60` to `Settings`.
- [ ] **Step 5: Update `.env.example`**
  Add `JWT_SECRET_KEY=dev-secret-key-change-in-production` to `.env.example`.
- [ ] **Step 6: Verify settings load**
  Run: `.venv/bin/python -c "from app.core.config import settings; print('JWT config verified:', bool(settings.JWT_SECRET_KEY))"`
  Expected: `JWT config verified: True`

---

### Task 2: User Model & Alembic Migration

**Files:**
- Create: `app/models/user.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/*_add_user_table.py`
- Test: `tests/test_user_model.py`

**Interfaces:**
- Produces: `UserRole(Enum)` with `ADMIN` and `USER`. `User(SQLModel, table=True)` table `users`.

- [ ] **Step 1: Write failing test in `tests/test_user_model.py`**
  ```python
  from app.models.user import User, UserRole
  from sqlmodel import Session, select

  def test_user_model_creation(session: Session):
      user = User(
          username="testadmin",
          email="admin@test.com",
          hashed_password="hashed_pw_placeholder",
          role=UserRole.ADMIN,
      )
      session.add(user)
      session.commit()
      session.refresh(user)
      assert user.id is not None
      assert user.role == UserRole.ADMIN
      assert user.is_active is True
  ```
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_user_model.py -q`
  Expected: FAIL with ModuleNotFoundError
- [ ] **Step 3: Implement `app/models/user.py`**
  Define `UserRole` and `User` model with `username` (unique, index), `email` (unique, index), `hashed_password`, `role`, `is_active`, and `created_at` (sa_type=sa.DateTime).
- [ ] **Step 4: Export `User` and `UserRole` in `app/models/__init__.py`**
- [ ] **Step 5: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_user_model.py -q`
  Expected: PASS
- [ ] **Step 6: Generate and apply Alembic migration for `users` table**
  Run: `.venv/bin/alembic revision --autogenerate -m "add_users_table"`
  Run: `.venv/bin/alembic upgrade head`
  Expected: Migration generated and applied to `traffic.db`.

---

### Task 3: Security & Token Utilities (`app/core/security.py`)

**Files:**
- Create: `app/core/security.py`
- Test: `tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str) -> str`
  - `verify_password(password: str, hashed_password: str) -> bool`
  - `create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str`
  - `decode_access_token(token: str) -> dict`

- [ ] **Step 1: Write failing tests in `tests/test_security.py`**
  ```python
  from app.core.security import hash_password, verify_password, create_access_token, decode_access_token

  def test_password_hashing():
      hashed = hash_password("secret123")
      assert hashed != "secret123"
      assert "$" in hashed
      assert verify_password("secret123", hashed) is True
      assert verify_password("wrongpw", hashed) is False

  def test_jwt_token_cycle():
      token = create_access_token({"sub": "1", "role": "ADMIN"})
      payload = decode_access_token(token)
      assert payload["sub"] == "1"
      assert payload["role"] == "ADMIN"
      assert "exp" in payload
  ```
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_security.py -q`
  Expected: FAIL with ModuleNotFoundError
- [ ] **Step 3: Implement `app/core/security.py`**
  Implement password hashing with `hashlib.pbkdf2_hmac` and token generation with `jwt.encode`/`jwt.decode` using `settings.JWT_SECRET_KEY` and algorithm `"HS256"`.
- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_security.py -q`
  Expected: PASS

---

### Task 4: Auth Schemas, Dependencies & Endpoints (`app/api/auth.py`)

**Files:**
- Create: `app/schemas/user.py`
- Create: `app/core/auth.py`
- Create: `app/api/auth.py`
- Modify: `app/main.py`
- Test: `tests/test_auth_api.py`

**Interfaces:**
- Produces:
  - `get_current_user` and `require_admin` FastAPI dependencies.
  - Endpoints: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`.

- [ ] **Step 1: Write failing tests in `tests/test_auth_api.py`**
  - Test registration: registers user, returns 201 with role `"USER"`.
  - Test registration ignores any client-supplied `role="ADMIN"`, ensuring role is always `"USER"`.
  - Test duplicate registration returns 400.
  - Test login with valid credentials (JSON payload) returns access token.
  - Test login with valid credentials (Form data) returns access token.
  - Test login with wrong password returns 401.
  - Test `GET /api/auth/me` with valid token returns user profile.
  - Test `GET /api/auth/me` without token returns 401.
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_auth_api.py -q`
  Expected: FAIL
- [ ] **Step 3: Implement `app/schemas/user.py`**
  Create `UserCreate` (username, email, password - no role field), `UserRead` (id, username, email, role, is_active, created_at), `UserLogin` (username, password), `TokenResponse` (access_token, token_type).
- [ ] **Step 4: Implement `app/core/auth.py`**
  Define `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")`.
  Implement `get_current_user` and `require_admin`.
- [ ] **Step 5: Implement `app/api/auth.py` and register in `app/main.py`**
  Implement `/register`, `/login` (handling both JSON body and Form data), and `/me`. Register router under `/api`.
- [ ] **Step 6: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_auth_api.py -q`
  Expected: PASS

---

### Task 5: Segment CRUD & RBAC Protection (`app/api/segments.py`)

**Files:**
- Modify: `app/schemas/segment.py`
- Modify: `app/api/segments.py`
- Test: `tests/test_segments_crud_rbac.py`

**Interfaces:**
- Consumes: `get_current_user`, `require_admin` from `app.core.auth`.
- Produces:
  - `GET /api/segments` and `GET /api/segments/{id}` protected by `get_current_user`.
  - `POST /api/segments`, `PUT /api/segments/{id}`, `DELETE /api/segments/{id}` protected by `require_admin`.
  - Schema `SegmentUpdate` with optional fields.

- [ ] **Step 1: Write failing tests in `tests/test_segments_crud_rbac.py`**
  - Test `GET /api/segments` without token returns 401.
  - Test `GET /api/segments` with regular User token returns 200.
  - Test `GET /api/segments/{id}` with regular User token returns 200 (or 404 if not found).
  - Test `POST /api/segments` with regular User token returns 403 Forbidden.
  - Test `POST /api/segments` with Admin token returns 201 Created.
  - Test `PUT /api/segments/{id}` with regular User token returns 403 Forbidden.
  - Test `PUT /api/segments/{id}` with Admin token updates fields and returns 200.
  - Test `DELETE /api/segments/{id}` with regular User token returns 403 Forbidden.
  - Test `DELETE /api/segments/{id}` with Admin token deletes segment and associated observations, returns 200.
  - Test `GET /api/segments/{id}/history` without token returns 401, with User token returns 200.
- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_segments_crud_rbac.py -q`
  Expected: FAIL
- [ ] **Step 3: Update `app/schemas/segment.py`**
  Add `SegmentUpdate` schema where all fields (`name`, `start_lat`, `start_lng`, `end_lat`, `end_lng`, `length_m`, `road_type`, `free_flow_speed_kmh`) are `Optional[...] = None`.
- [ ] **Step 4: Update `app/api/segments.py`**
  - Add `GET /api/segments/{id}` endpoint.
  - Protect `GET /api/segments`, `GET /api/segments/{id}`, and `GET /api/segments/{id}/history` with `get_current_user`.
  - Protect `POST /api/segments`, `PUT /api/segments/{id}`, and `DELETE /api/segments/{id}` with `require_admin`.
  - In `delete_segment`: query and delete all `TrafficObservation` where `segment_id == id` before deleting the `Segment`.
- [ ] **Step 5: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_segments_crud_rbac.py -q`
  Expected: PASS

---

### Task 6: Seed Script Update & Test Suite Fixture Migration

**Files:**
- Modify: `scripts/seed_demo.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_segments.py`

**Interfaces:**
- Produces: Default Admin (`admin / admin123`) and User (`user / user123`) seeded by `scripts/seed_demo.py`. Fixtures `admin_token_headers` and `user_token_headers` in `tests/conftest.py`.

- [ ] **Step 1: Update `scripts/seed_demo.py`**
  Add creation of default Admin (`admin`, `admin@traffic.local`, password `admin123`, role `ADMIN`) and default User (`user`, `user@traffic.local`, password `user123`, role `USER`) if they do not already exist.
- [ ] **Step 2: Update `tests/conftest.py`**
  Add helper fixtures `admin_user`, `regular_user`, `admin_headers`, `user_headers` for authenticated API client tests.
- [ ] **Step 3: Update existing `tests/test_segments.py`**
  Update calls to `GET /api/segments` and `GET /api/segments/{id}/history` in `test_segments.py` to pass authenticated headers so existing tests reflect the new auth requirement.
- [ ] **Step 4: Run seed demo script**
  Run: `.venv/bin/python scripts/seed_demo.py`
  Expected: Success output reporting Admin and User accounts seeded.

---

### Task 7: Comprehensive Verification & Regression Testing

**Files:**
- Modify: `README.md` (keep <= 10 lines)
- Test: All tests in `tests/`

- [ ] **Step 1: Run full test suite**
  Run: `.venv/bin/pytest -q`
  Expected: All tests pass with 0 failures.
- [ ] **Step 2: Verify OpenAPI schema includes auth and updated segment CRUD**
  Run: `.venv/bin/python -c "from app.main import app; schema = app.openapi(); paths = list(schema['paths'].keys()); assert '/api/auth/login' in paths; assert '/api/auth/register' in paths; assert '/api/auth/me' in paths; print('OpenAPI verified, paths:', paths)"`
  Expected: Success output.
- [ ] **Step 3: End-to-end fresh database lifecycle verification**
  Run:
  ```bash
  DATABASE_URL=sqlite:///./auth_e2e_test.db .venv/bin/alembic upgrade head
  DATABASE_URL=sqlite:///./auth_e2e_test.db .venv/bin/python scripts/seed_demo.py
  DATABASE_URL=sqlite:///./auth_e2e_test.db .venv/bin/python -c "from app.main import app; app.openapi()"
  rm -f auth_e2e_test.db
  ```
  Expected: All commands exit 0.
