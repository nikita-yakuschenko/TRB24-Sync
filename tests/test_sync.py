from markers import clean_description
from sync import Sync, tags_of


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

    def get_issue(self, _issue_id: str) -> dict:
        return self.issue

    def create_issue(self, project: str, summary: str, description: str, _assignee) -> dict:
        self.created = {"project": project, "summary": summary, "description": description}
        return {"idReadable": "COL-99"}

    def update_issue(self, *_a, **_k) -> None:
        return None


class _BX:
    def __init__(self, task: dict | None = None) -> None:
        self.task = task or {}
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


class _Settings:
    bitrix_group_id = 987
    bitrix_responsible = "1"
    user_map = {}
    youtrack_base = "https://tracker.avgst.ru"
    portal_base = "https://avgstroy.bitrix24.ru"


def test_skip_b2b_hub():
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
