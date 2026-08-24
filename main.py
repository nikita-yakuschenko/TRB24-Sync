from urllib.parse import parse_qs

from fastapi import FastAPI, Header, HTTPException, Query, Request

from bitrix_client import Bitrix
from bitrix_events import task_id_from_event
from settings import Settings
from store import PairStore
from sync import Sync
from youtrack_client import YouTrack

app = FastAPI(title="YouTrack × Bitrix24 sync")
_sync: Sync | None = None


def get_sync() -> Sync:
    global _sync
    if _sync is None:
        settings = Settings()
        _sync = Sync(
            settings,
            PairStore(settings.sqlite_path),
            YouTrack(settings.youtrack_base, settings.yt_headers()),
            Bitrix(settings.bitrix_webhook),
        )
    return _sync


def _check_secret(
    secret: str | None,
    header: str | None,
    youtrack_token: str | None = None,
) -> None:
    expected = get_sync().settings.webhook_secret
    if not expected:
        return
    got = secret or ""
    if header and header.startswith("Bearer "):
        got = got or header[7:]
    if youtrack_token:
        got = got or youtrack_token
    if got != expected:
        raise HTTPException(status_code=401, detail="bad secret")


@app.get("/health")
def health() -> dict:
    sync = get_sync()
    sync.store.ping()
    return {"status": "ok"}


@app.post("/hooks/youtrack")
async def youtrack_hook(
    request: Request,
    secret: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    x_youtrack_token: str | None = Header(default=None, alias="X-YouTrack-Token"),
) -> dict:
    _check_secret(secret, authorization, x_youtrack_token)
    payload = await request.json()
    issue_id = payload.get("id") or payload.get("issueId")
    nested = payload.get("issue") or {}
    if not issue_id:
        issue_id = nested.get("id") or nested.get("idReadable")
    if not issue_id:
        raise HTTPException(status_code=400, detail="no issue id")
    return get_sync().on_youtrack(str(issue_id))


@app.post("/hooks/bitrix")
async def bitrix_hook(
    request: Request,
    secret: str | None = Query(default=None),
) -> dict:
    _check_secret(secret, None)
    ctype = request.headers.get("content-type", "")
    if "json" in ctype:
        payload = await request.json()
    else:
        raw = (await request.body()).decode("utf-8")
        payload = _form_to_dict(raw)
    task_id = task_id_from_event(payload)
    if not task_id:
        return {"ok": True, "skip": "not-a-task-event"}
    event = str(payload.get("event") or payload.get("EVENT") or "").upper()
    if event == "ONTASKDELETE":
        return {"ok": True, "skip": "delete-ignored"}
    return get_sync().on_bitrix(task_id)


def _form_to_dict(raw: str) -> dict:
    parsed = {k: v[-1] for k, v in parse_qs(raw, keep_blank_values=True).items()}
    nested: dict = {"event": parsed.get("event") or parsed.get("EVENT")}
    after_id = parsed.get("data[FIELDS_AFTER][ID]") or parsed.get("data[FIELDS_BEFORE][ID]")
    if after_id:
        nested["data"] = {"FIELDS_AFTER": {"ID": after_id}}
    return nested
