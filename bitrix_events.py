# Входящий вебхук Bitrix: JSON приложения или form-urlencoded исходящего хука.


def task_id_from_event(payload: dict) -> str | None:
    event = str(payload.get("event") or payload.get("EVENT") or "").upper()
    if event and event not in {"ONTASKADD", "ONTASKUPDATE", "ONTASKDELETE"}:
        return None
    data = payload.get("data") or payload.get("DATA") or {}
    if isinstance(data, dict):
        after = data.get("FIELDS_AFTER") or data.get("fields_after") or {}
        before = data.get("FIELDS_BEFORE") or data.get("fields_before") or {}
        for block in (after, before):
            if isinstance(block, dict) and block.get("ID"):
                return str(block["ID"])
        if data.get("ID"):
            return str(data["ID"])
    if payload.get("ID"):
        return str(payload["ID"])
    return None
