"""OWNER: Rohit. HTTP API — exactly the contract in the design doc.
Run:  cd backend && MOCK=1 uvicorn app.main:app --reload --port 8000
"""
import asyncio

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app import orchestrator
from app.config import MAX_BUDGET_USD, modes
from app.contracts import ApproveBody, AuditResponse, CreateRunResponse, RejectBody, Run
from app.data import audit, store
from app.events import bus

app = FastAPI(title="Roomie API")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])

_TASKS: set[asyncio.Task] = set()
ALLOWED_STORES = {"shopify", "amazon", "walmart"}


class ApiException(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiException)
async def _api_exc(_: Request, e: ApiException):
    return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})


@app.exception_handler(Exception)
async def _any_exc(_: Request, e: Exception):
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL", "message": repr(e)[:300]}})


def _get_run(run_id: str) -> Run:
    run = store.load_run(run_id)
    if not run:
        raise ApiException(404, "RUN_NOT_FOUND", f"No run {run_id}")
    return run


@app.get("/api/health")
def health():
    return {"ok": True, "modes": modes()}


@app.post("/api/runs", status_code=201, response_model=CreateRunResponse)
async def create_run(photo: UploadFile | None = File(None), user_id: str = Form(...),
                     budget_usd: float = Form(...), stores: str = Form("shopify,amazon,walmart"),
                     note: str = Form("")):
    image = await photo.read() if photo else None
    if image is not None and len(image) == 0:
        image = None
    if image is None and not note.strip():
        raise ApiException(400, "BAD_INPUT", "Send a photo, a note, or both")
    if image and len(image) > 8 * 1024 * 1024:
        raise ApiException(400, "BAD_INPUT", "Photo must be 8 MB or smaller")
    if not (0 < budget_usd <= MAX_BUDGET_USD):
        raise ApiException(400, "BAD_INPUT", f"budget_usd must be between 0 and {MAX_BUDGET_USD:.0f}")
    store_list = [s.strip() for s in stores.split(",") if s.strip()]
    if not store_list or not set(store_list) <= ALLOWED_STORES:
        raise ApiException(400, "BAD_INPUT", "stores must be a comma list of shopify,amazon,walmart")

    run = Run(id=orchestrator.new_run_id(), user_id=user_id.strip() or "anon", state="created",
              budget_usd=round(budget_usd, 2), stores=store_list, note=note.strip())
    store.save_run(run)
    media_type = (photo.content_type if photo else None) or "image/jpeg"
    if image:
        orchestrator.PHOTOS[run.id] = (image, media_type)
    t = asyncio.create_task(orchestrator.plan(run, image, media_type))
    _TASKS.add(t)
    t.add_done_callback(_TASKS.discard)
    return CreateRunResponse(run_id=run.id, state="analyzing")


@app.get("/api/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    return _get_run(run_id)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    _get_run(run_id)
    return StreamingResponse(bus(run_id).stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/runs/{run_id}/photo")
def run_photo(run_id: str):
    if run_id not in orchestrator.PHOTOS:
        raise ApiException(404, "RUN_NOT_FOUND", "No photo for this run")
    data, mt = orchestrator.PHOTOS[run_id]
    return Response(content=data, media_type=mt)


@app.post("/api/runs/{run_id}/approve", response_model=Run)
async def approve(run_id: str, body: ApproveBody):
    run = _get_run(run_id)
    if run.state != "awaiting_approval":
        raise ApiException(409, "INVALID_STATE", f"Run is {run.state}, not awaiting approval")
    unknown = set(body.selected_item_ids) - {i.id for i in run.items}
    if unknown:
        raise ApiException(400, "BAD_INPUT", f"Unknown item ids: {sorted(unknown)}")
    run.state = "executing"            # claim it before any await so a double tap can't approve twice
    store.save_run(run)
    return await orchestrator.approve(run, body.selected_item_ids)


@app.post("/api/runs/{run_id}/reject", response_model=Run)
async def reject(run_id: str, body: RejectBody):
    run = _get_run(run_id)
    if run.state != "awaiting_approval":
        raise ApiException(409, "INVALID_STATE", f"Run is {run.state}, not awaiting approval")
    return await orchestrator.reject(run, body.reason)


@app.get("/api/runs/{run_id}/audit", response_model=AuditResponse)
def get_audit(run_id: str):
    _get_run(run_id)
    return AuditResponse(events=audit.list_events(run_id), chain_valid=audit.verify_chain(run_id))
