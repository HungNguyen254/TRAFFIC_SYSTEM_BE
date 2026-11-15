# Refactor TrafficService to Use Database Instead of CSV - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển đổi toàn bộ logic nạp dữ liệu giao thông trong `TrafficService` từ việc đọc tệp tĩnh `synthetic_traffic_dataset.csv` sang truy vấn từ bảng cơ sở dữ liệu `TrafficData`, xóa bỏ hoàn toàn phụ thuộc vào file CSV.

**Architecture:** Xóa bỏ `import csv` và `SYNTHETIC_CSV` trong `app/services/traffic_service.py`. Cung cấp hàm `_load_traffic_data_from_db(session)` truy vấn trực tiếp từ bảng `TrafficData` kết hợp in-memory cache có thread-lock và hàm `clear_traffic_data_cache()` để làm mới khi dữ liệu thay đổi. Cập nhật `get_edge_traffic_snapshot` nhận `session` tùy chọn.

**Tech Stack:** Python 3.14, SQLModel / SQLAlchemy, FastAPI, Pytest.

**Spec:** Quyết định kiến trúc đã thống nhất trong phiên làm việc.

## Global Constraints

- Không làm thay đổi giao diện trả về của API `GET /api/v1/traffic/edges/status` và `GET /api/v1/traffic/edges/summary`.
- Tuyệt đối không đọc file CSV trong `app/services/`.
- Đảm bảo thread-safety với `threading.Lock` khi đọc/lưu cache bộ nhớ.
- Tất cả các bài test (28 bài hiện có + bài test mới) phải vượt qua 100%.

---

### Task 1: Chuyển đổi `TrafficService` sang Đọc Dữ Liệu từ Bảng `TrafficData`

**Files:**
- Modify: `app/services/traffic_service.py:1-40, 120-155, 308-330, 360-370, 455-465`
- Modify: `app/api/v1/endpoints/admin.py:18-25` (gọi clear_traffic_data_cache khi retrain)
- Test: `tests/test_traffic_service_db.py`

**Interfaces:**
- Consumes:
  - `app.models.traffic_data.TrafficData`
  - `app.core.database.engine`
- Produces:
  - `app.services.traffic_service.clear_traffic_data_cache() -> None`
  - `app.services.traffic_service.TrafficService.get_edge_traffic_snapshot(edge: Edge, hour_of_day: int, day_of_week: int, session: Session | None = None) -> dict`

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_traffic_service_db.py`:
- Khởi tạo SQLite in-memory, tạo tables `Edge`, `Node`, `TrafficData`.
- Chèn bản ghi `TrafficData` cho `EDGE_TEST_01`.
- Kiểm tra `TrafficService.get_edge_traffic_snapshot` tính toán đúng vận tốc từ bảng `TrafficData` mà không cần file CSV.
- Kiểm tra fallback về tốc độ mặc định nếu edge chưa có dữ liệu trong `TrafficData`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_traffic_service_db.py -v`
Expected: FAIL (vì TrafficService hiện tại vẫn cố đọc từ `SYNTHETIC_CSV`).

- [ ] **Step 3: Implement `_load_traffic_data_from_db` và cập nhật `TrafficService`**

1. Trong `app/services/traffic_service.py`:
   - Xóa `import csv`, `DATA_DIR = Path("data")`, `SYNTHETIC_CSV = ...`.
   - Import `threading` và `from app.models.traffic_data import TrafficData`, `from app.core.database import engine`.
   - Viết `_load_traffic_data_from_db(session)` và `clear_traffic_data_cache()`.
   - Cập nhật `get_edge_traffic_snapshot` nhận `session: Session | None = None` và gọi `_load_traffic_data_from_db(session)`.
   - Cập nhật các vị trí gọi trong `get_edges_status` và `get_traffic_summary` để truyền `session`.
2. Trong `app/api/v1/endpoints/admin.py`:
   - Gọi `clear_traffic_data_cache()` trong `_run_retraining()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_traffic_service_db.py -v`
Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/pytest -v`
Expected: 29/29 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/traffic_service.py app/api/v1/endpoints/admin.py tests/test_traffic_service_db.py
git commit -m "feat(traffic_service): load traffic status from TrafficData database table instead of CSV"
```
