# Traffic Forecasting API
```bash
uv pip install -r requirements.txt
alembic upgrade head
python scripts/seed_demo.py
python scripts/train_model.py
uvicorn app.main:app --port 8000
pytest -q
```
