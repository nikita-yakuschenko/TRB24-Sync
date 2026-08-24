from catalog import FROM_TRACKER_TAG, KEY_TO_NAME, SKIP_KEYS, key_for_tags
from markers import clean_description, parse_bitrix_id, parse_youtrack_id

# Bitrix: 2 ждать, 3 в работе, 5 завершена
STATUS_OPEN = "2"
STATUS_IN_PROGRESS = "3"
STATUS_DONE = "5"
IN_PROGRESS_STATES = {"In Progress", "В работе"}


def assignee_login(issue: dict) -> str | None:
    for field in issue.get("customFields") or []:
        if field.get("name") == "Assignee":
            value = field.get("value") or {}
            if isinstance(value, dict):
                return value.get("login")
    return None


def is_resolved(issue: dict) -> bool:
    return issue.get("resolved") not in (None, False, "")


def state_name(issue: dict) -> str | None:
    for field in issue.get("customFields") or []:
        if field.get("name") == "State":
            value = field.get("value") or {}
            if isinstance(value, dict):
                return value.get("name")
    return None


def bitrix_open_status(issue: dict) -> str:
    # «В работе» в трекере = status 3 в портале. Остальное открытое = ждать.
    if state_name(issue) in IN_PROGRESS_STATES:
        return STATUS_IN_PROGRESS
    return STATUS_OPEN


def tags_of(task: dict) -> list[str]:
    raw = task.get("tags") or task.get("TAGS") or []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    names = []
    if isinstance(raw, dict):
        items = raw.values()
    else:
        items = raw
    for item in items:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            names.append(str(item.get("title") or item.get("name") or ""))
    return [n for n in names if n]


def xml_id(task: dict) -> str:
    return str(task.get("xmlId") or task.get("XML_ID") or "")


class Sync:
    def __init__(self, settings, store, youtrack, bitrix) -> None:
        self.settings = settings
        self.store = store
        self.youtrack = youtrack
        self.bitrix = bitrix

    def on_youtrack(self, issue_id: str) -> dict:
        issue = self.youtrack.get_issue(issue_id)
        if not issue:
            return {"ok": True, "skip": "not-ready"}
        readable = issue.get("idReadable") or issue_id
        project = (issue.get("project") or {}).get("shortName") or ""
        if project in SKIP_KEYS:
            return {"ok": True, "skip": "own-project"}
        pair = self.store.get_by_youtrack(readable)
        closed = None
        if pair and is_resolved(issue):
            closed = self._close_bitrix(pair["bitrix_id"])
        from_bitrix = bool(parse_bitrix_id(issue.get("description"))) or (
            pair and pair["source"] == "bitrix"
        )
        if from_bitrix:
            out = {"ok": True, "skip": "from-bitrix"}
            if closed:
                out["closed"] = closed
            return out
        title = f"{readable}: {issue.get('summary') or ''}".strip()
        desc = clean_description(issue.get("description"))
        tags = [KEY_TO_NAME.get(project, project), FROM_TRACKER_TAG]
        responsible = self._responsible(assignee_login(issue))
        fields = {
            "TITLE": title,
            "DESCRIPTION": desc,
            "GROUP_ID": self.settings.bitrix_group_id,
            "RESPONSIBLE_ID": responsible,
            "XML_ID": f"YT:{readable}",
            "TAGS": tags,
        }
        # Закрытие — только complete(). STATUS на update канбан «Неразобранное» не закрывает.
        if is_resolved(issue):
            if not pair:
                fields["STATUS"] = STATUS_DONE
        else:
            fields["STATUS"] = bitrix_open_status(issue)
        if pair:
            self.bitrix.task_update(pair["bitrix_id"], fields)
            out = {"ok": True, "updated": pair["bitrix_id"]}
            if closed:
                out["closed"] = closed
            return out
        created = self.bitrix.task_add(fields)
        bx_id = str(created.get("id") or created.get("ID"))
        self.store.put(readable, bx_id, "youtrack", project)
        if is_resolved(issue):
            closed = self._close_bitrix(bx_id)
        out = {"ok": True, "created": bx_id}
        if closed:
            out["closed"] = closed
        return out

    def on_bitrix(self, task_id: str) -> dict:
        task = self.bitrix.task_get(task_id)
        description = task.get("description") or task.get("DESCRIPTION") or ""
        if xml_id(task).startswith("YT:") or parse_youtrack_id(description):
            return {"ok": True, "skip": "from-youtrack"}
        if FROM_TRACKER_TAG in tags_of(task):
            return {"ok": True, "skip": "from-youtrack-tag"}
        pair = self.store.get_by_bitrix(task_id)
        title = (task.get("title") or task.get("TITLE") or "").strip() or f"Bitrix {task_id}"
        try:
            key = key_for_tags(tags_of(task))
        except ValueError as err:
            return {"ok": False, "error": str(err)}
        if not key:
            return {"ok": True, "skip": "no-route-tag"}
        desc = clean_description(description)
        if pair:
            self.youtrack.update_issue(pair["youtrack_id"], title, desc)
            return {"ok": True, "updated": pair["youtrack_id"]}
        created = self.youtrack.create_issue(key, title, desc, None)
        readable = created.get("idReadable")
        self.store.put(readable, str(task_id), "bitrix", key)
        return {"ok": True, "created": readable}

    def _close_bitrix(self, bitrix_id: str) -> str | None:
        task = self.bitrix.task_get(bitrix_id)
        status = str(task.get("status") or task.get("STATUS") or "")
        if status in {STATUS_DONE, "4"}:
            return None
        self.bitrix.task_complete(bitrix_id)
        return str(bitrix_id)

    def _responsible(self, login: str | None) -> int:
        if login and login in self.settings.user_map:
            return self.settings.user_map[login]
        if self.settings.bitrix_responsible:
            return int(self.settings.bitrix_responsible)
        raise RuntimeError("нет BITRIX_DEFAULT_RESPONSIBLE_ID и нет USER_MAP")
