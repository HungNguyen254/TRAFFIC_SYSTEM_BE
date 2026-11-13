# Edge Traffic Status by Bounding Box and Area Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng API trả về tình trạng giao thông mới nhất của các đoạn đường (edges) theo khung bản đồ (bounding box) hoặc theo khu vực (district/area), kèm thời điểm cập nhật (`updated_at`), và tạo Pull Request nộp bài.

**Architecture:** Tạo endpoint mới `GET /api/v1/edges/status` và nâng cấp endpoint `GET /api/v1/edges`. Dùng Pydantic schema xác thực tham số bounding box và trả về schema chuẩn hóa chứa thông tin chi tiết từng đoạn đường (tốc độ, mức độ ùn tắc, nhãn mô tả, tọa độ đầu cuối) cùng timestamp `updated_at`. Lọc dữ liệu trong `TrafficService` dựa trên tọa độ `Node` và địa giới `district`.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy, Pydantic v2, Python 3.14, unittest, Starlette TestClient, Git & GitHub CLI (`gh`).

**Spec:** [docs/superpowers/specs/2026-11-13-edge-traffic-status-bbox-area-design.md](file:///home/PageNguyen/Projects/BE/docs/superpowers/specs/2026-11-13-edge-traffic-status-bbox-area-design.md)

## Global Constraints
- Python >= 3.14, tương thích môi trường hiện có của repo.
- Tương thích ngược: `GET /api/v1/edges` vẫn hoạt động bình thường đối với các client không truyền bbox/district.
- Lọc theo quận/khu vực hỗ trợ không phân biệt hoa thường và không phân biệt dấu tiếng Việt (thông qua hàm `strip_accents`).
- Thời điểm cập nhật `updated_at` sử dụng ISO-8601 (UTC hoặc Asia/Ho_Chi_Minh).

## Review Focus
1. Bounding box coordinates validation: `min_lat > max_lat` hoặc `min_lng > max_lng` phải trả về lỗi `400 Bad Request` rõ ràng, không để xảy ra lỗi 500.
2. Định dạng chuỗi `bbox`: Chuỗi `bbox="min_lng,min_lat,max_lng,max_lat"` phân tách bằng dấu phẩy phải được parse chính xác; nếu sai định dạng phải báo lỗi 400.
3. Edge nằm ở ranh giới bounding box: Đoạn đường có 1 điểm trong box và 1 điểm ngoài box vẫn được coi là nằm trong khung nhìn bản đồ.
4. Tìm kiếm khu vực không dấu: Tìm kiếm `dong da`, `Dong Da` hoặc `Đống Đa` đều phải trả về đúng các đoạn đường thuộc quận Đống Đa.
5. Kiểm tra trường `updated_at`: Cả cấp response gốc và từng item trong danh sách đoạn đường đều có trường `updated_at` hợp lệ.

---

### Task 1: Schemas for Edge Traffic Status

**Files:**
- Create: `app/schemas/edge_status.py`
- Test: `tests/test_schemas_edge_status.py`

**Interfaces:**
- Produces:
  - `NodeBrief`: `node_code: str`, `node_name: str`, `district: str | None`, `lat: float`, `lng: float`
  - `EdgeStatusItem`: `edge_id: uuid.UUID`, `edge_code: str`, `street_name: str`, `length_km: float`, `max_speed_limit: int`, `from_node: NodeBrief | None`, `to_node: NodeBrief | None`, `speed: float`, `congestion_level: int`, `congestion_text: str`, `updated_at: datetime`
  - `EdgeStatusResponse`: `total: int`, `updated_at: datetime`, `filters: dict`, `edges: list[EdgeStatusItem]`
  - `parse_bbox_param(bbox: str | None, min_lat: float | None, min_lng: float | None, max_lat: float | None, max_lng: float | None) -> tuple[float | None, float | None, float | None, float | None]`

- [ ] **Step 1: Write the failing test**

Viết test trong `tests/test_schemas_edge_status.py` kiểm tra khởi tạo `EdgeStatusItem`, `EdgeStatusResponse`, và logic phân tích tọa độ `parse_bbox_param`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_schemas_edge_status.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.edge_status'`

- [ ] **Step 3: Implement `app/schemas/edge_status.py`**

Định nghĩa các Pydantic BaseModel: `NodeBrief`, `EdgeStatusItem`, `EdgeStatusResponse`, và helper function `parse_bbox_param` để parse chuỗi bbox / 4 tọa độ riêng rẽ và kiểm tra tính hợp lệ (`min <= max`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_schemas_edge_status.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add app/schemas/edge_status.py tests/test_schemas_edge_status.py
git commit -m "feat(schemas): add edge status response and bbox parsing schemas"
```

---

### Task 2: TrafficService Filtering & Status Calculation

**Files:**
- Modify: `app/services/traffic_service.py`
- Test: `tests/test_traffic_service_status.py`

**Interfaces:**
- Consumes:
  - `app/schemas/edge_status.py`: `EdgeStatusItem`, `EdgeStatusResponse`, `NodeBrief`
- Produces:
  - `TrafficService.get_edges_status(session, min_lat=None, min_lng=None, max_lat=None, max_lng=None, district=None, hour_of_day=None, day_of_week=None) -> EdgeStatusResponse`
  - Cập nhật `TrafficService.get_edges_with_traffic(...)` nhận thêm các tham số `min_lat, min_lng, max_lat, max_lng, district` và trả về thêm trường `updated_at`.

- [ ] **Step 1: Write the failing test**

Viết test trong `tests/test_traffic_service_status.py` dựng mock session SQLModel với một số Node và Edge mẫu ở các quận khác nhau (Đống Đa, Cầu Giấy, etc.) và kiểm tra:
1. Lọc theo bounding box trả về đúng số edge.
2. Lọc theo district (có dấu và không dấu) trả về đúng edges.
3. Kết quả trả về chứa `updated_at`, `speed`, `congestion_level`, `congestion_text`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_traffic_service_status.py`
Expected: FAIL with `AttributeError: type object 'TrafficService' has no attribute 'get_edges_status'`

- [ ] **Step 3: Implement `get_edges_status` in `app/services/traffic_service.py`**

Thêm logic tính toán nhãn `congestion_text`:
- 1: "Thông thoáng"
- 2: "Di chuyển chậm"
- 3: "Ùn tắc nghiêm trọng"
- 4: "Kẹt xe hoàn toàn"
Thực hiện hàm `get_edges_status` và cập nhật `get_edges_with_traffic` để hỗ trợ lọc theo bbox và district.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_traffic_service_status.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/traffic_service.py tests/test_traffic_service_status.py
git commit -m "feat(service): implement get_edges_status with bbox and area filters"
```

---

### Task 3: API Endpoint `GET /api/v1/edges/status` and `GET /api/v1/edges`

**Files:**
- Modify: `app/api/v1/endpoints/edges.py`
- Test: `tests/test_api_edges_status.py`

**Interfaces:**
- Consumes:
  - `TrafficService.get_edges_status`
  - `parse_bbox_param`
  - `EdgeStatusResponse`
- Produces:
  - `GET /api/v1/edges/status` endpoint
  - Nâng cấp `GET /api/v1/edges` endpoint

- [ ] **Step 1: Write the failing test**

Viết integration test trong `tests/test_api_edges_status.py` sử dụng `starlette.testclient.TestClient(app)`:
- `GET /api/v1/edges/status` trả về 200 kèm `status_code=200`, `data.updated_at`, `data.edges`.
- `GET /api/v1/edges/status?bbox=105.80,20.99,105.83,21.04` lọc đúng các đoạn trong bbox.
- `GET /api/v1/edges/status?district=dong da` lọc đúng các đoạn thuộc Đống Đa.
- `GET /api/v1/edges/status?min_lat=21.05&max_lat=21.01` trả về 400 Bad Request.
- `GET /api/v1/edges` vẫn trả về 200 và có thêm `updated_at`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_api_edges_status.py`
Expected: FAIL (404 Not Found for `/api/v1/edges/status` or missing query parameters)

- [ ] **Step 3: Implement endpoint in `app/api/v1/endpoints/edges.py`**

Định nghĩa endpoint `GET /api/v1/edges/status` với đầy đủ query parameters (`bbox`, `min_lat`, `min_lng`, `max_lat`, `max_lng`, `district`, `area`, `hour`, `day_of_week`), rate limiter, xử lý lỗi 400 khi tọa độ không hợp lệ, và cập nhật `GET /api/v1/edges`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_api_edges_status.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/endpoints/edges.py tests/test_api_edges_status.py
git commit -m "feat(api): add GET /api/v1/edges/status endpoint and upgrade /edges"
```

---

### Task 4: Full Verification, Branch Push & PR Creation

**Files:**
- Run full test suite: `uv run python -m unittest discover -s tests -p "test_*.py"`
- Create branch `feature/api-traffic-status-bbox-area`
- Push to remote: `git push -u origin feature/api-traffic-status-bbox-area`
- Create PR: `gh pr create --title "feat: API tra tinh trang giao thong theo bounding box hoac khu vuc" --body "..."`

- [ ] **Step 1: Run full test suite**

Run: `uv run python -m unittest discover -s tests -p "test_*.py"`
Expected: ALL TESTS PASS

- [ ] **Step 2: Push git branch to GitHub**

Run: `git push -u origin feature/api-traffic-status-bbox-area`
Expected: Pushed branch successfully

- [ ] **Step 3: Create GitHub Pull Request**

Run: `gh pr create --title "feat: API tra tinh trang doan duong theo bounding box hoac khu vuc" --body "..."`
Expected: Pull Request URL returned (e.g., https://github.com/HungNguyen254/TRAFFIC_SYSTEM_BE/pull/XX)

- [ ] **Step 4: Final verification and submission**

Kiểm tra link PR trả về và trình bày cho người dùng.
