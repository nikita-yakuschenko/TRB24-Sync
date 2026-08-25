from catalog import FROM_TRACKER_TAG, KEY_TO_NAME, SKIP_KEYS, key_for_tags
from markers import clean_description, parse_bitrix_id, parse_youtrack_id

# Bitrix: 2 ждать, 3 в работе, 5 завершена. Канбан группы — это STAGE, не STATUS.
STATUS_OPEN = "2"
STATUS_IN_PROGRESS = "3"
STATUS_DONE = "5"
IN_PROGRESS_STATES = {"In Progress", "В работе"}
OPEN_STATES = {"Open", "Открыта"}
DONE_STATES = {"Done", "Завершена"}
# Колонки канбана 987 → три AMS-состояния. Тестирование всё ещё работа.
STAGE_IN_PROGRESS = {"в работе", "тестирование", "возвращено в работу"}
STAGE_DONE = {"готово"}


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


def youtrack_id_from_task(task: dict) -> str | None:
    xml = xml_id(task)
    if xml.upper().startswith("YT:"):
        readable = xml.split(":", 1)[1].strip()
        return readable or None
    desc = task.get("description") or task.get("DESCRIPTION") or ""
    return parse_youtrack_id(desc)


def from_youtrack_card(task: dict) -> bool:
    return bool(youtrack_id_from_task(task)) or FROM_TRACKER_TAG in tags_of(task)


def youtrack_state_from_bitrix(task: dict, stage_title: str | None) -> str:
    # Канбан «В работе» оставляет STATUS=2 — стадия главнее системного статуса.
    title = (stage_title or "").strip().lower()
    if title in STAGE_DONE:
        return "Done"
    if title in STAGE_IN_PROGRESS:
        return "In Progress"
    status = str(task.get("status") or task.get("STATUS") or "")
    if status in {STATUS_DONE, "4"}:
        return "Done"
    if status == STATUS_IN_PROGRESS:
        return "In Progress"
    return "Open"


def same_ams_state(current: str | None, desired: str) -> bool:
    buckets = {"Open": OPEN_STATES, "In Progress": IN_PROGRESS_STATES, "Done": DONE_STATES}
    return bool(current) and current in buckets.get(desired, {desired})


class Sync:
    def __init__(self, settings, store, youtrack, bitrix) -> None:
        self.settings = settings
        self.store = store
        self.youtrack = youtrack
        self.bitrix = bitrix
        self._stage_titles: dict[str, dict[str, str]] = {}

    def on_youtrack(self, issue_id: str) -> dict:
        issue = self.youtrack.get_issue(issue_id)
        if not issue:
            return {"ok": True, "skip": "not-ready"}
        readable = issue.get("idReadable") or issue_id
        project = (issue.get("project") or {}).get("shortName") or ""
        if project in SKIP_KEYS:
            # Витрину для хаба не создаём. Закрытие уже существующей карточки в 987 — да.
            if is_resolved(issue):
                bx_id = self._bitrix_id_for(readable)
                if bx_id:
                    closed = self._close_bitrix(bx_id)
                    out = {"ok": True, "skip": "own-project"}
                    if closed:
                        out["closed"] = closed
                    return out
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
        pair = self.store.get_by_bitrix(task_id)
        yt_id = youtrack_id_from_task(task) or (pair["youtrack_id"] if pair else None)
        desired = youtrack_state_from_bitrix(task, self._stage_title(task))
        if from_youtrack_card(task):
            # Витрина: заголовок не трогаем, State с канбана 987 — да.
            if not yt_id:
                return {"ok": True, "skip": "from-youtrack"}
            return self._set_youtrack_state(yt_id, desired)
        title = (task.get("title") or task.get("TITLE") or "").strip() or f"Bitrix {task_id}"
        try:
            key = key_for_tags(tags_of(task))
        except ValueError as err:
            return {"ok": False, "error": str(err)}
        if not key:
            return {"ok": True, "skip": "no-route-tag"}
        desc = clean_description(description)
        if pair:
            self.youtrack.update_issue(pair["youtrack_id"], title, desc, state=desired)
            return {"ok": True, "updated": pair["youtrack_id"], "state": desired}
        created = self.youtrack.create_issue(key, title, desc, None)
        readable = created.get("idReadable")
        self.store.put(readable, str(task_id), "bitrix", key)
        if desired != "Open":
            self.youtrack.update_issue(readable, state=desired)
        return {"ok": True, "created": readable, "state": desired}

    def _set_youtrack_state(self, yt_id: str, desired: str) -> dict:
        issue = self.youtrack.get_issue(yt_id)
        current = state_name(issue) if issue else None
        if same_ams_state(current, desired):
            return {"ok": True, "skip": "state-already", "updated": yt_id, "state": desired}
        # План — трекер: канбан 987 не открывает уже закрытую карточку.
        if issue and is_resolved(issue) and desired != "Done":
            return {"ok": True, "skip": "yt-resolved", "updated": yt_id, "state": current}
        self.youtrack.update_issue(yt_id, state=desired)
        return {"ok": True, "updated": yt_id, "state": desired}

    def _bitrix_id_for(self, readable: str) -> str | None:
        pair = self.store.get_by_youtrack(readable)
        if pair:
            return pair["bitrix_id"]
        return self.bitrix.task_find_by_xml_id(f"YT:{readable}", self.settings.bitrix_group_id)

    def _stages_for(self, gid: str) -> dict[str, str]:
        cache = self._stage_titles.get(gid)
        if cache is None:
            raw = self.bitrix.task_stages(gid) or {}
            cache = {}
            items = raw.values() if isinstance(raw, dict) else raw
            for row in items:
                if isinstance(row, dict):
                    cache[str(row.get("ID") or "")] = str(row.get("TITLE") or "")
            self._stage_titles[gid] = cache
        return cache

    def _stage_title(self, task: dict) -> str:
        sid = str(task.get("stageId") or task.get("STAGE_ID") or "")
        if not sid:
            return ""
        gid = str(task.get("groupId") or task.get("GROUP_ID") or self.settings.bitrix_group_id)
        return self._stages_for(gid).get(sid, "")

    def _done_stage_id(self, task: dict) -> str | None:
        gid = str(task.get("groupId") or task.get("GROUP_ID") or self.settings.bitrix_group_id)
        for sid, title in self._stages_for(gid).items():
            if (title or "").strip().lower() in STAGE_DONE:
                return sid
        return None

    def _close_bitrix(self, bitrix_id: str) -> str | None:
        task = self.bitrix.task_get(bitrix_id)
        status = str(task.get("status") or task.get("STATUS") or "")
        stage = (self._stage_title(task) or "").strip().lower()
        did = False
        if status not in {STATUS_DONE, "4"}:
            self.bitrix.task_complete(bitrix_id)
            did = True
        sid = self._done_stage_id(task)
        if sid and stage not in STAGE_DONE:
            self.bitrix.task_update(bitrix_id, {"STAGE_ID": sid})
            did = True
        return str(bitrix_id) if did else None

    def _responsible(self, login: str | None) -> int:
        if login and login in self.settings.user_map:
            return self.settings.user_map[login]
        if self.settings.bitrix_responsible:
            return int(self.settings.bitrix_responsible)
        raise RuntimeError("нет BITRIX_DEFAULT_RESPONSIBLE_ID и нет USER_MAP")
