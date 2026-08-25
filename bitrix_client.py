import httpx


class Bitrix:
    def __init__(self, webhook_base: str) -> None:
        self.base = webhook_base.rstrip("/") + "/"

    def _call(self, method: str, params: dict) -> dict:
        url = f"{self.base}{method}.json"
        with httpx.Client(timeout=30) as client:
            r = client.post(url, json=params)
            r.raise_for_status()
            data = r.json()
        if data.get("error"):
            raise RuntimeError(f"{method}: {data.get('error_description') or data['error']}")
        return data.get("result") or {}

    def task_get(self, task_id: str | int) -> dict:
        # Без TAGS в select портал не отдаёт теги — маршрут Bitrix→YouTrack молчит.
        result = self._call(
            "tasks.task.get",
            {"taskId": int(task_id), "select": ["*", "TAGS"]},
        )
        return result.get("task") or result

    def task_add(self, fields: dict) -> dict:
        result = self._call("tasks.task.add", {"fields": fields})
        return result.get("task") or result

    def task_update(self, task_id: str | int, fields: dict) -> None:
        self._call("tasks.task.update", {"taskId": int(task_id), "fields": fields})

    def task_complete(self, task_id: str | int) -> None:
        # Канбан «Неразобранное» не закрывается полем STATUS в update.
        self._call("tasks.task.complete", {"taskId": int(task_id)})

    def task_stages(self, group_id: str | int) -> dict:
        # Колонки канбана группы. Перенос карточки пишет STAGE_ID, не STATUS.
        return self._call("task.stages.get", {"entityId": int(group_id), "isAdmin": "Y"}) or {}
