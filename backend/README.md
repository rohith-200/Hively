# Roomie backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env            # fill in what you have
MOCK=1 uvicorn app.main:app --reload --port 8000    # everything mocked, full flow works
```

Smoke test:
```bash
curl localhost:8000/api/health
curl -F photo=@kitchen.jpg -F user_id=priya -F budget_usd=400 localhost:8000/api/runs
curl -N localhost:8000/api/runs/<run_id>/events
```

## Who edits what (keep function signatures; contracts in `app/contracts.py`)
| File | Owner | Replace mock with |
|---|---|---|
| `app/llm/__init__.py` | Jaideep | Nebius calls behind `USE_NEBIUS` |
| `app/data/store.py` | Suman | SingleStore search + runs behind `USE_SINGLESTORE` |
| `app/data/audit.py` | Suman | `audit_events` table (hash algorithm already final) |
| `app/data/memory.py` | Suman | Cognee behind `USE_COGNEE`, keep local fallback |
| `app/data/analytics.py` | Suman | Amplitude behind `USE_AMPLITUDE` |
| `app/main.py`, `app/orchestrator.py`, `app/events.py` | Rohit | — |
| `app/commerce/payments.py`, `app/commerce/merchants.py` | Rohit | real when `USE_STRIPE=1` / `USE_SHOPIFY=1` |

Fixtures for the frontend: `fixtures/` (regenerate with `python -m scripts.make_fixtures`).
