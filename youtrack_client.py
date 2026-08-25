import time

import httpx

ISSUE_FIELDS = (
    "id,idReadable,summary,description,resolved,"
    "project(shortName,name),"
    "customFields(name,value(name,login))"
)


class YouTrack:
    def __init__(self, base: str, headers: dict[str, str]) -> None:
        self.base = base.rstrip("/")
        self.headers = headers

    def get_issue(self, issue_id: str) -> dict | None:
        # Хук может прийти до коммита транзакции: 404 — не 500, иначе workflow откатывает карточку.
        url = f"{self.base}/api/issues/{issue_id}"
        with httpx.Client(timeout=30) as client:
            last = None
            for _ in range(5):
                last = client.get(url, headers=self.headers, params={"fields": ISSUE_FIELDS})
                if last.status_code != 404:
                    last.raise_for_status()
                    return last.json()
                time.sleep(0.5)
            return None

    def create_issue(self, project: str, summary: str, description: str, assignee_login: str | None) -> dict:
        body: dict = {
            "project": {"shortName": project},
            "summary": summary,
            "description": description,
        }
        if assignee_login:
            body["customFields"] = [{"name": "Assignee", "$type": "SingleUserIssueCustomField", "value": {"login": assignee_login}}]
        with httpx.Client(timeout=30) as client:
            r = client.post(
                f"{self.base}/api/issues",
                headers=self.headers,
                params={"fields": ISSUE_FIELDS},
                json=body,
            )
            r.raise_for_status()
            return r.json()

    def update_issue(
        self,
        issue_id: str,
        summary: str | None = None,
        description: str | None = None,
        state: str | None = None,
    ) -> None:
        payload: dict = {}
        if summary is not None:
            payload["summary"] = summary
        if description is not None:
            payload["description"] = description
        if state:
            payload["customFields"] = [
                {
                    "name": "State",
                    "$type": "StateIssueCustomField",
                    "value": {"name": state},
                }
            ]
        if not payload:
            return
        with httpx.Client(timeout=30) as client:
            r = client.post(
                f"{self.base}/api/issues/{issue_id}",
                headers=self.headers,
                json=payload,
            )
            r.raise_for_status()
