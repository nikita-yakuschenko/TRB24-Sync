from catalog import FROM_TRACKER_TAG, KEY_TO_NAME, SKIP_KEYS, key_for_tags
from markers import bitrix_marker, parse_bitrix_id, parse_youtrack_id, youtrack_marker

# Bitrix: 2 ждать, 3 в работе, 5 завершена
STATUS_OPEN = "2"
STATUS_DONE = "5"


def assignee_login(issue: dict) -> str | None:
    for field in issue.get("customFields") or []:
        if field.get("name") == "Assignee":
            value = field.get("value") or {}
            if isinstance(value, dict):
                return value.get("login")
    return None


def is_resolved(issue: dict) -> bool:
    return issue.get("resolved") not in (None, False, "")


def tags_of(task: dict) -> list[str]:
    raw = task.get("tags") or task.get("TAGS") or []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    names = []
    for item in raw:
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
        readable = issue.get("idReadable") or issue_id
        project = (issue.get("project") or {}).get("shortName") or ""
        if project in SKIP_KEYS:
            return {"ok": True, "skip": "own-project"}
        if parse_bitrix_id(issue.get("description")):
            return {"ok": True, "skip": "from-bitrix"}
        pair = self.store.get_by_youtrack(readable)
        title = f"{readable}: {issue.get('summary') or ''}".strip()
        desc = self._bitrix_description(issue, readable)
        tags = [KEY_TO_NAME.get(project, project), FROM_TRACKER_TAG]
        responsible = self._responsible(assignee_login(issue))
        fields = {
            "TITLE": title,
            "DESCRIPTION": desc,
            "GROUP_ID": self.settings.bitrix_group_id,
            "RESPONSIBLE_ID": responsible,
            "XML_ID": f"YT:{readable}",
            "TAGS": ", ".join(tags),
            "STATUS": STATUS_DONE if is_resolved(issue) else STATUS_OPEN,
        }
        if pair:
            self.bitrix.task_update(pair["bitrix_id"], fields)
            return {"ok": True, "updated": pair["bitrix_id"]}
        created = self.bitrix.task_add(fields)
        bx_id = str(created.get("id") or created.get("ID"))
        self.store.put(readable, bx_id, "youtrack", project)
        return {"ok": True, "created": bx_id}

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
        desc = self._youtrack_description(task, task_id, description)
        if pair:
            self.youtrack.update_issue(pair["youtrack_id"], title, desc)
            return {"ok": True, "updated": pair["youtrack_id"]}
        created = self.youtrack.create_issue(key, title, desc, None)
        readable = created.get("idReadable")
        self.store.put(readable, str(task_id), "bitrix", key)
        return {"ok": True, "created": readable}

    def _responsible(self, login: str | None) -> int:
        if login and login in self.settings.user_map:
            return self.settings.user_map[login]
        if self.settings.bitrix_responsible:
            return int(self.settings.bitrix_responsible)
        raise RuntimeError("нет BITRIX_DEFAULT_RESPONSIBLE_ID и нет USER_MAP")

    def _bitrix_description(self, issue: dict, readable: str) -> str:
        body = issue.get("description") or ""
        url = f"{self.settings.youtrack_base}/issue/{readable}"
        return f"{youtrack_marker(readable)}\n\n{body}\n\nТрекер: {url}".strip()

    def _youtrack_description(self, task: dict, task_id: str, body: str) -> str:
        view = f"{self.settings.portal_base}/workgroups/group/{self.settings.bitrix_group_id}/tasks/task/view/{task_id}/"
        return f"{bitrix_marker(task_id)}\n\n{body}\n\nBitrix: {view}".strip()
