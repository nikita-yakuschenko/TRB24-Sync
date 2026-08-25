from markers import clean_description
from sync import Sync, tags_of, youtrack_state_from_bitrix


class _Store:
    def __init__(self) -> None:
        self.rows: dict = {}

    def get_by_youtrack(self, issue_id: str):
        return self.rows.get(("yt", issue_id))

    def get_by_bitrix(self, task_id: str):
        return self.rows.get(("bx", str(task_id)))

    def put(self, youtrack_id: str, bitrix_id: str, source: str, project_key: str) -> None:
        row = {
            "youtrack_id": youtrack_id,
            "bitrix_id": str(bitrix_id),
            "source": source,
            "project_key": project_key,
        }
        self.rows[("yt", youtrack_id)] = row
        self.rows[("bx", str(bitrix_id))] = row


class _YT:
    def __init__(self, issue: dict) -> None:
        self.issue = issue
        self.created = None
        self.updated = None

    def get_issue(self, _issue_id: str) -> dict:
        return self.issue

    def create_issue(self, project: str, summary: str, description: str, _assignee) -> dict:
        self.created = {"project": project, "summary": summary, "description": description}
        return {"idReadable": "COL-99"}

    def update_issue(self, issue_id, summary=None, description=None, state=None) -> None:
        self.updated = {
            "id": issue_id,
            "summary": summary,
            "description": description,
            "state": state,
        }


class _BX:
    def __init__(self, task: dict | None = None, stages: dict | None = None, xml_ids: dict | None = None) -> None:
        self.task = task or {}
        self.stages = stages or {}
        self.xml_ids = xml_ids or {}
        self.added = None
        self.updated = None
        self.completed = None

    def task_get(self, _task_id: str) -> dict:
        return self.task

    def task_add(self, fields: dict) -> dict:
        self.added = fields
        return {"id": "1"}

    def task_update(self, task_id, fields: dict) -> None:
        self.updated = {"id": str(task_id), "fields": fields}

    def task_complete(self, task_id) -> None:
        self.completed = str(task_id)

    def task_stages(self, _group_id) -> dict:
        return self.stages

    def task_find_by_xml_id(self, xml: str, _group_id) -> str | None:
        return (self.xml_ids or {}).get(xml)


class _Settings:
    bitrix_group_id = 987
    bitrix_responsible = "1"
    user_map = {}
    youtrack_base = "https://tracker.avgst.ru"
    portal_base = "https://avgstroy.bitrix24.ru"


def test_youtrack_not_ready_is_skip():
    class _Missing:
        def get_issue(self, _issue_id: str):
            return None

    out = Sync(_Settings(), _Store(), _Missing(), _BX()).on_youtrack("B24-4")
    assert out == {"ok": True, "skip": "not-ready"}


def test_skip_asl_and_site():
    for key, readable in (("ASL", "ASL-1"), ("SITE", "SITE-1")):
        yt = _YT({"idReadable": readable, "summary": "x", "description": "", "project": {"shortName": key}})
        out = Sync(_Settings(), _Store(), yt, _BX()).on_youtrack(readable)
        assert out["skip"] == "own-project"
    yt = _YT({"idReadable": "B2B-1", "summary": "хаб", "description": "", "project": {"shortName": "B2B"}})
    out = Sync(_Settings(), _Store(), yt, _BX()).on_youtrack("B2B-1")
    assert out["skip"] == "own-project"


def test_clean_drops_html_and_footers():
    raw = "<!-- sync:youtrack:COL-9 -->\nТекст\n\nТрекер: https://x\nBitrix: https://y"
    assert clean_description(raw) == "Текст"


def test_from_bitrix_does_not_write_back():
    store = _Store()
    store.put("COL-9", "373317", "bitrix", "COL")
    yt = _YT({"idReadable": "COL-9", "summary": "заявка", "description": "тело", "project": {"shortName": "COL"}})
    bx = _BX()
    out = Sync(_Settings(), store, yt, bx).on_youtrack("COL-9")
    assert out["skip"] == "from-bitrix"
    assert bx.added is None
    assert bx.updated is None
    assert bx.completed is None


def test_resolved_from_bitrix_closes_bitrix():
    store = _Store()
    store.put("COL-10", "373319", "bitrix", "COL")
    yt = _YT(
        {
            "idReadable": "COL-10",
            "summary": "заявка",
            "description": "тело",
            "resolved": 1756032556000,
            "project": {"shortName": "COL"},
        }
    )
    bx = _BX({"status": "2"})
    out = Sync(_Settings(), store, yt, bx).on_youtrack("COL-10")
    assert out["skip"] == "from-bitrix"
    assert out["closed"] == "373319"
    assert bx.completed == "373319"
    assert bx.added is None
    assert bx.updated is None


def test_resolved_from_youtrack_closes_bitrix():
    store = _Store()
    store.put("COL-9", "373317", "youtrack", "COL")
    yt = _YT(
        {
            "idReadable": "COL-9",
            "summary": "зеркало",
            "description": "тело",
            "resolved": 1756032227000,
            "project": {"shortName": "COL"},
        }
    )
    bx = _BX({"status": "2"})
    out = Sync(_Settings(), store, yt, bx).on_youtrack("COL-9")
    assert out["updated"] == "373317"
    assert out["closed"] == "373317"
    assert bx.completed == "373317"
    assert "STATUS" not in bx.updated["fields"]


def test_already_completed_bitrix_is_left_alone():
    store = _Store()
    store.put("COL-10", "373319", "bitrix", "COL")
    yt = _YT(
        {
            "idReadable": "COL-10",
            "summary": "заявка",
            "description": "тело",
            "resolved": 1,
            "project": {"shortName": "COL"},
        }
    )
    bx = _BX({"status": "5"})
    out = Sync(_Settings(), store, yt, bx).on_youtrack("COL-10")
    assert out["skip"] == "from-bitrix"
    assert "closed" not in out
    assert bx.completed is None


def test_bitrix_card_has_no_sync_comment():
    yt = _YT({"idReadable": "COL-10", "summary": "правка OL", "description": "как в трекере", "project": {"shortName": "COL"}})
    bx = _BX()
    Sync(_Settings(), _Store(), yt, bx).on_youtrack("COL-10")
    assert "sync:youtrack" not in (bx.added["DESCRIPTION"] or "")
    assert bx.added["DESCRIPTION"] == "как в трекере"
    assert bx.added["TITLE"].startswith("COL-10:")
    assert bx.added["STATUS"] == "2"


def _yt_issue(state: str, resolved=None):
    return {
        "idReadable": "TRK-1",
        "summary": "пин образа",
        "description": "тело",
        "resolved": resolved,
        "project": {"shortName": "TRK"},
        "customFields": [{"name": "State", "value": {"name": state}}],
    }


def test_in_progress_creates_bitrix_status_3():
    bx = _BX()
    Sync(_Settings(), _Store(), _YT(_yt_issue("In Progress")), bx).on_youtrack("TRK-1")
    assert bx.added["STATUS"] == "3"


def test_in_progress_russian_creates_bitrix_status_3():
    bx = _BX()
    Sync(_Settings(), _Store(), _YT(_yt_issue("В работе")), bx).on_youtrack("TRK-1")
    assert bx.added["STATUS"] == "3"


def test_in_progress_updates_existing_bitrix_status():
    store = _Store()
    store.put("TRK-1", "373461", "youtrack", "TRK")
    bx = _BX()
    out = Sync(_Settings(), store, _YT(_yt_issue("In Progress")), bx).on_youtrack("TRK-1")
    assert out["updated"] == "373461"
    assert bx.updated["fields"]["STATUS"] == "3"
    assert bx.completed is None


def test_open_updates_bitrix_waiting_status():
    store = _Store()
    store.put("TRK-1", "373461", "youtrack", "TRK")
    bx = _BX()
    Sync(_Settings(), store, _YT(_yt_issue("Open")), bx).on_youtrack("TRK-1")
    assert bx.updated["fields"]["STATUS"] == "2"


def test_tags_from_bitrix_map():
    names = tags_of({"tags": {"7053": {"id": 7053, "title": "Open Lines ДомКлик"}}})
    assert names == ["Open Lines ДомКлик"]
    task = {
        "title": "Нет ответа в OL",
        "description": "клиент ждёт",
        "tags": [{"title": "Open Lines ДомКлик"}],
        "xmlId": "",
    }
    yt = _YT({})
    out = Sync(_Settings(), _Store(), yt, _BX(task)).on_bitrix("555")
    assert out["created"] == "COL-99"
    assert yt.created["project"] == "COL"
    assert yt.created["summary"] == "Нет ответа в OL"
    assert "sync:bitrix" not in yt.created["description"]
    assert yt.created["description"] == "клиент ждёт"
    assert out["state"] == "Open"


GROUP_STAGES = {
    "2579": {"ID": "2579", "TITLE": "В работе"},
    "2587": {"ID": "2587", "TITLE": "Бэклог"},
    "2573": {"ID": "2573", "TITLE": "Готово"},
}


def _bx_from_yt(stage_id="2579", status="2"):
    return {
        "title": "B2B-2: Почта",
        "description": "",
        "xmlId": "YT:B2B-2",
        "status": status,
        "stageId": stage_id,
        "groupId": "987",
        "tags": [{"title": "из YouTrack"}, {"title": "b2b-Партнёрский кабинет"}],
    }


def test_bitrix_stage_maps_to_ams_state():
    assert youtrack_state_from_bitrix({"status": "2"}, "В работе") == "In Progress"
    assert youtrack_state_from_bitrix({"status": "2"}, "Тестирование") == "In Progress"
    assert youtrack_state_from_bitrix({"status": "2"}, "Бэклог") == "Open"
    assert youtrack_state_from_bitrix({"status": "2"}, "Готово") == "Done"
    assert youtrack_state_from_bitrix({"status": "3"}, "") == "In Progress"


def test_kanban_in_progress_sets_youtrack_state():
    yt = _YT(
        {
            "idReadable": "B2B-2",
            "customFields": [{"name": "State", "value": {"name": "Open"}}],
        }
    )
    out = Sync(_Settings(), _Store(), yt, _BX(_bx_from_yt(), GROUP_STAGES)).on_bitrix("373471")
    assert out == {"ok": True, "updated": "B2B-2", "state": "In Progress"}
    assert yt.updated["id"] == "B2B-2"
    assert yt.updated["state"] == "In Progress"
    assert yt.updated["summary"] is None
    assert yt.created is None


def test_kanban_already_in_progress_is_noop():
    yt = _YT(
        {
            "idReadable": "B2B-2",
            "customFields": [{"name": "State", "value": {"name": "В работе"}}],
        }
    )
    out = Sync(_Settings(), _Store(), yt, _BX(_bx_from_yt(), GROUP_STAGES)).on_bitrix("373471")
    assert out["skip"] == "state-already"
    assert yt.updated is None


def test_kanban_backlog_sets_open():
    yt = _YT(
        {
            "idReadable": "B2B-2",
            "customFields": [{"name": "State", "value": {"name": "In Progress"}}],
        }
    )
    out = Sync(_Settings(), _Store(), yt, _BX(_bx_from_yt("2587"), GROUP_STAGES)).on_bitrix("373471")
    assert out["state"] == "Open"
    assert yt.updated["state"] == "Open"


def test_from_youtrack_tag_without_id_still_skips():
    task = {
        "title": "без пары",
        "xmlId": "",
        "status": "2",
        "tags": [{"title": "из YouTrack"}],
    }
    yt = _YT({})
    out = Sync(_Settings(), _Store(), yt, _BX(task)).on_bitrix("1")
    assert out["skip"] == "from-youtrack"
    assert yt.updated is None
    assert yt.created is None


def _b2b_resolved():
    return {
        "idReadable": "B2B-2",
        "summary": "почта",
        "description": "",
        "resolved": 1,
        "project": {"shortName": "B2B"},
        "customFields": [{"name": "State", "value": {"name": "Done"}}],
    }


def test_b2b_resolved_closes_bitrix_from_store():
    store = _Store()
    store.put("B2B-2", "373471", "youtrack", "B2B")
    bx = _BX({"status": "2", "stageId": "2579", "groupId": "987"}, GROUP_STAGES)
    out = Sync(_Settings(), store, _YT(_b2b_resolved()), bx).on_youtrack("B2B-2")
    assert out["skip"] == "own-project"
    assert out["closed"] == "373471"
    assert bx.completed == "373471"
    assert bx.updated["fields"]["STAGE_ID"] == "2573"
    assert bx.added is None


def test_b2b_resolved_finds_xml_without_store():
    bx = _BX(
        {"status": "2", "stageId": "2579", "groupId": "987"},
        GROUP_STAGES,
        xml_ids={"YT:B2B-2": "373471"},
    )
    out = Sync(_Settings(), _Store(), _YT(_b2b_resolved()), bx).on_youtrack("B2B-2")
    assert out["closed"] == "373471"
    assert bx.completed == "373471"
    assert bx.added is None


def test_kanban_does_not_reopen_resolved_youtrack():
    yt = _YT(_b2b_resolved())
    out = Sync(_Settings(), _Store(), yt, _BX(_bx_from_yt(), GROUP_STAGES)).on_bitrix("373471")
    assert out["skip"] == "yt-resolved"
    assert yt.updated is None
