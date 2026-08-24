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
