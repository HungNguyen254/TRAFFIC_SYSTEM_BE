# Security Vulnerabilities Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate all confirmed and prioritized security vulnerabilities identified in `REPORT.md` across authentication, forecast persistence, token lifecycle, information disclosure, and graph query caching.

**Architecture:** 
1. Fix package namespace collision by switching `jwt` (1.4.0) to `PyJWT` in dependencies and virtual environment.
2. Remove unauthenticated database mutation and commit operations from `PredictionService.get_forecast`, enforce input bounds (`max_length=24`) on forecast timeline requests, and attach slowapi rate limiting.
3. Implement `token_version` tracking on `User` models, embedding it into JWT claims and checking it during token authentication to invalidate tokens immediately upon password changes.
4. Redact raw internal driver and database exception strings from public health check responses to prevent diagnostic leaks.
5. Implement in-memory caching for road network graph construction (`build_graph`) keyed by `weight_mode` with TTL/invalidation support to stop full-table scans per request.
6. Add configuration validation rejecting default JWT dev secrets in non-development environments.

**Tech Stack:** Python 3.14, FastAPI, SQLModel / SQLAlchemy, PyJWT, NetworkX, SlowAPI, Pydantic, Pytest.

**Spec:** `/home/PageNguyen/Projects/BE/REPORT.md`

## Global Constraints

- Do not break existing API contracts or response schemas (`StandardResponse` envelope).
- Preserve existing authentication interfaces and hashing schemes (`Argon2id`).
- All changes must be backed by unit/integration tests running under pytest.
- Strict isolation of write operations in read-only / projection endpoints.

## Review Focus

- Token version verification must handle both legacy/missing claims gracefully without unhandled exceptions.
- Password change must reliably revoke older tokens while newly issued tokens after password change must succeed.
- Graph cache must correctly separate `distance` and `duration` weight modes.
- Forecast endpoint must retain accurate calculation and response structure without calling `session.commit()` or modifying `Prediction` table rows.
- Health check must still report `"connected"` when DB is healthy and `"disconnected"` without raw exception strings when DB fails.

---

### Task 1: Fix PyPI Package Namespace Collision in JWT Dependency

**Files:**
- Modify: `requirements.txt:31`
- Test: `tests/test_security_jwt.py`

**Interfaces:**
- Consumes: `app.core.security.create_access_token`, `app.core.security.decode_access_token`
- Produces: Working PyJWT module functions `jwt.encode`, `jwt.decode`, `jwt.PyJWTError`

- [ ] **Step 1: Write the failing test for JWT encode/decode and PyJWT error handling**

```python
# tests/test_security_jwt.py
import pytest
import jwt
from app.core.security import create_access_token, decode_access_token

def test_jwt_package_is_pyjwt():
    assert hasattr(jwt, "encode")
    assert hasattr(jwt, "decode")
    assert hasattr(jwt, "PyJWTError")

def test_token_encode_and_decode_roundtrip():
    token = create_access_token({"sub": "test-uuid", "role": "user"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "test-uuid"
    assert payload["role"] == "user"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_security_jwt.py -v`
Expected: FAIL (AttributeError: module 'jwt' has no attribute 'PyJWTError' or 'encode')

- [ ] **Step 3: Update `requirements.txt` and install `PyJWT`**

Replace `jwt==1.4.0` in `requirements.txt` with `PyJWT>=2.8.0`.
Run `uv pip uninstall jwt` and `uv pip install "PyJWT>=2.8.0"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_security_jwt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_security_jwt.py
git commit -m "fix(security): replace jwt package with PyJWT to resolve namespace collision"
```

---

### Task 2: Remediate Unauthenticated Forecast State Mutation & Input Unboundedness

**Files:**
- Modify: `app/services/prediction_service.py:230-254`
- Modify: `app/schemas/prediction.py:15-19`
- Modify: `app/api/v1/endpoints/predictions.py:11-20`
- Test: `tests/test_prediction_security.py`

**Interfaces:**
- Consumes: `PredictionRequest`, `PredictionService.get_forecast`
- Produces: `get_forecast` returning `PredictionResponse` without calling `_save_or_update_prediction` or `session.commit()`; `minutes_ahead` with `max_length=24`; rate-limited route.

- [ ] **Step 1: Write the failing tests for forecast read-only behavior and payload length limits**

```python
# tests/test_prediction_security.py
from datetime import datetime, UTC
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from app.schemas.prediction import PredictionRequest
from app.services.prediction_service import PredictionService
from app.models.edge import Edge

def test_prediction_request_max_length_minutes_ahead():
    with pytest.raises(ValidationError):
        PredictionRequest(minutes_ahead=list(range(1, 26)))

def test_get_forecast_does_not_commit_or_save(monkeypatch):
    mock_session = MagicMock()
    mock_edge = Edge(edge_id="00000000-0000-0000-0000-000000000001", max_speed_limit=50, street_name="Test St", length_km=1.0, from_node_id="00000000-0000-0000-0000-000000000002", to_node_id="00000000-0000-0000-0000-000000000003")
    mock_session.get.return_value = mock_edge
    
    mock_save = MagicMock()
    monkeypatch.setattr(PredictionService, "_save_or_update_prediction", mock_save)

    req = PredictionRequest(edge_id=mock_edge.edge_id, minutes_ahead=[30, 60])
    res = PredictionService.get_forecast(mock_session, req)

    assert res.edge_id == mock_edge.edge_id
    mock_save.assert_not_called()
    mock_session.commit.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_prediction_security.py -v`
Expected: FAIL

- [ ] **Step 3: Implement fixes in prediction schema, service, and endpoint**

1. In `app/schemas/prediction.py`: add `max_length=24` to `minutes_ahead` Field.
2. In `app/services/prediction_service.py`: in `get_forecast`, remove lines calling `cls._save_or_update_prediction` and `session.commit()`.
3. In `app/api/v1/endpoints/predictions.py`: import `limiter` and decorate `get_traffic_forecast` with `@limiter.limit("10/minute")`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_prediction_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/prediction.py app/services/prediction_service.py app/api/v1/endpoints/predictions.py tests/test_prediction_security.py
git commit -m "fix(security): prevent unauthenticated DB pollution and rate limit forecast endpoint"
```

---

### Task 3: Invalidate Access Tokens on User Password Change

**Files:**
- Modify: `app/models/user.py:10-19`
- Modify: `app/services/auth_service.py:44,61-63`
- Modify: `app/core/security.py:46-60`
- Test: `tests/test_auth_token_revocation.py`

**Interfaces:**
- Consumes: `User.token_version`, `create_access_token(data={"token_version": ...})`
- Produces: Invalidated previous tokens when `change_password` increments `user.token_version`.

- [ ] **Step 1: Write the failing tests for password change token revocation**

```python
# tests/test_auth_token_revocation.py
import uuid
import pytest
from unittest.mock import MagicMock
from sqlmodel import Session, SQLModel, create_engine, select
from app.models.user import User
from app.services.auth_service import AuthService
from app.core.security import create_access_token, decode_access_token, get_optional_user, hash_password
from app.schemas.auth import ChangePasswordRequest

def test_password_change_increments_token_version_and_invalidates_old_token():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            user_id=uuid.uuid4(),
            email="test@example.com",
            password_hash=hash_password("CurrentPassword123!"),
            full_name="Test User",
            token_version=1
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        old_token = create_access_token({"sub": str(user.user_id), "role": user.role, "token_version": user.token_version})
        
        # Test old token resolves user
        mock_auth = MagicMock(credentials=old_token)
        resolved_user = get_optional_user(mock_auth, session)
        assert resolved_user is not None
        assert resolved_user.user_id == user.user_id

        # Change password
        AuthService.change_password(
            session,
            user,
            ChangePasswordRequest(current_password="CurrentPassword123!", new_password="NewPassword456!")
        )
        session.refresh(user)
        assert user.token_version == 2

        # Old token must now be rejected
        resolved_user_after = get_optional_user(mock_auth, session)
        assert resolved_user_after is None

        # New token with token_version=2 works
        new_token = create_access_token({"sub": str(user.user_id), "role": user.role, "token_version": user.token_version})
        mock_auth_new = MagicMock(credentials=new_token)
        assert get_optional_user(mock_auth_new, session) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_auth_token_revocation.py -v`
Expected: FAIL (no token_version attribute or token still valid after password change)

- [ ] **Step 3: Implement token_version in User model, AuthService, and Security dependency**

1. In `app/models/user.py`: add `token_version: int = Field(default=1, nullable=False)` to `User`.
2. In `app/services/auth_service.py`:
   - In `authenticate_user`: pass `"token_version": user.token_version` into `create_access_token`.
   - In `change_password`: increment `user.token_version += 1`.
3. In `app/core/security.py`:
   - In `get_optional_user`: check `if payload.get("token_version") != user.token_version: return None`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_auth_token_revocation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/user.py app/services/auth_service.py app/core/security.py tests/test_auth_token_revocation.py
git commit -m "fix(security): invalidate active access tokens upon user password change"
```

---

### Task 4: Prevent Information Disclosure in Health Check

**Files:**
- Modify: `app/main.py:68-79`
- Test: `tests/test_health_disclosure.py`

**Interfaces:**
- Consumes: `/api/health`
- Produces: Generic `"disconnected"` database status and server-side log, without driver details or host disclosures.

- [ ] **Step 1: Write the failing test for health check error disclosure**

```python
# tests/test_health_disclosure.py
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.main import app

def test_health_check_does_not_leak_exception_details(monkeypatch):
    def mock_check_db_connection():
        raise OperationalError("connection to server at 'db.internal.supabase.co' (10.0.0.5), port 5432 failed: FATAL: password authentication failed", None, None)
    
    monkeypatch.setattr("app.main.check_db_connection", mock_check_db_connection)
    
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["database"] == "disconnected"
    assert "db.internal.supabase.co" not in response.text
    assert "password authentication failed" not in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_health_disclosure.py -v`
Expected: FAIL

- [ ] **Step 3: Implement sanitized database status and server-side logging in `app/main.py`**

In `app/main.py`:
Replace `db_status = f"error: {exc}"` with:
```python
logger.error("Health check database probe failed: %s", exc)
db_status = "disconnected"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_health_disclosure.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_health_disclosure.py
git commit -m "fix(security): sanitize database error details in public health check"
```

---

### Task 5: Add Road Network Graph In-Memory Caching

**Files:**
- Modify: `app/services/routing_service.py:16-85`
- Test: `tests/test_routing_cache.py`

**Interfaces:**
- Consumes: `build_graph(session, weight_mode)`
- Produces: Cached `TrafficGraph` avoiding repeated SQL full-table scans. Includes `clear_graph_cache()`.

- [ ] **Step 1: Write the failing test for routing graph caching**

```python
# tests/test_routing_cache.py
from unittest.mock import MagicMock
import uuid
from sqlmodel import Session
from app.models.node import Node
from app.models.edge import Edge
from app.services.routing_service import build_graph, clear_graph_cache

def test_build_graph_caches_result(monkeypatch):
    clear_graph_cache()
    mock_session = MagicMock(spec=Session)
    node1 = Node(node_id=uuid.uuid4(), node_code="N1", node_name="Node 1", latitude=21.0, longitude=105.8)
    node2 = Node(node_id=uuid.uuid4(), node_code="N2", node_name="Node 2", latitude=21.1, longitude=105.9)
    edge = Edge(edge_id=uuid.uuid4(), edge_code="E1", street_name="St", from_node_id=node1.node_id, to_node_id=node2.node_id, length_km=1.0, max_speed_limit=40)
    
    mock_session.exec.side_effect = [
        MagicMock(all=lambda: [node1, node2]),
        MagicMock(all=lambda: [edge]),
    ]
    
    # First call: executes queries
    g1 = build_graph(mock_session, weight_mode="distance")
    assert mock_session.exec.call_count == 2

    # Second call with same weight_mode: served from cache, no DB query
    g2 = build_graph(mock_session, weight_mode="distance")
    assert g1 is g2
    assert mock_session.exec.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_routing_cache.py -v`
Expected: FAIL

- [ ] **Step 3: Implement in-memory cache and `clear_graph_cache` in `app/services/routing_service.py`**

Add thread-safe / in-memory dictionary caching with TTL and force_refresh support:
```python
_GRAPH_CACHE: dict[WeightMode, tuple[float, TrafficGraph]] = {}
GRAPH_CACHE_TTL_SECONDS = 300.0

def clear_graph_cache() -> None:
    _GRAPH_CACHE.clear()
```
Inside `build_graph`: check cache before executing DB queries; update cache when built.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_routing_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/routing_service.py tests/test_routing_cache.py
git commit -m "perf(routing): add in-memory caching to build_graph to prevent repeated table scans"
```

---

### Task 6: Enforce Secure JWT Secret in Non-Dev Environments

**Files:**
- Modify: `app/core/config.py:1-31`
- Test: `tests/test_config_security.py`

**Interfaces:**
- Consumes: `Settings`
- Produces: Validation error when `ENVIRONMENT != "dev"` and `JWT_SECRET_KEY` uses the default dev secret.

- [ ] **Step 1: Write the failing test for configuration secret validation**

```python
# tests/test_config_security.py
import pytest
from pydantic import ValidationError
from app.core.config import Settings

def test_dev_environment_permits_default_secret():
    s = Settings(ENVIRONMENT="dev")
    assert s.JWT_SECRET_KEY.startswith("dev-secret-key")

def test_prod_environment_rejects_default_secret():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="prod", JWT_SECRET_KEY="dev-secret-key-change-in-production-must-be-long-enough")

def test_prod_environment_accepts_custom_secret():
    s = Settings(ENVIRONMENT="prod", JWT_SECRET_KEY="super-secure-production-random-secret-key-here")
    assert s.JWT_SECRET_KEY == "super-secure-production-random-secret-key-here"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_config_security.py -v`
Expected: FAIL

- [ ] **Step 3: Implement model validator in `app/core/config.py`**

Add `model_validator` to `Settings` verifying that when `ENVIRONMENT != "dev"`, `JWT_SECRET_KEY` must not match `"dev-secret-key-change-in-production-must-be-long-enough"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_config_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py tests/test_config_security.py
git commit -m "fix(security): enforce secure JWT secret key in non-dev environments"
```

---

### Task 7: Full Verification and Regression Test Suite

**Files:**
- Modify: `tests/` (all test files)
- Verify: All tests pass

- [ ] **Step 1: Run the complete test suite**

Run: `./.venv/bin/pytest -v`
Expected: All tests pass cleanly.

- [ ] **Step 2: Verify git status and clean state**

Run: `git status`
Expected: Working tree clean, all files tracked and tests passing.
