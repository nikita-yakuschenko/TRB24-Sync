import os


def _req(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"нет {name}")
    return value


class Settings:
    def __init__(self) -> None:
        self.youtrack_base = os.environ.get("YOUTRACK_BASE_URL", "https://tracker.avgst.ru").rstrip("/")
        self.youtrack_token = os.environ.get("YOUTRACK_TOKEN", "")
        self.bitrix_webhook = os.environ.get("BITRIX_WEBHOOK_URL", "").rstrip("/") + "/"
        self.bitrix_group_id = int(os.environ.get("BITRIX_GROUP_ID", "987"))
        self.bitrix_responsible = os.environ.get("BITRIX_DEFAULT_RESPONSIBLE_ID", "")
        self.webhook_secret = os.environ.get("WEBHOOK_SECRET", "")
        self.sqlite_path = os.environ.get("SQLITE_PATH", "/data/sync.sqlite")
        self.portal_base = os.environ.get(
            "BITRIX_PORTAL_URL", "https://avgstroy.bitrix24.ru"
        ).rstrip("/")
        # login YouTrack → id пользователя Bitrix, через запятую: n.yakuschenko:1
        self.user_map = _parse_user_map(os.environ.get("USER_MAP", ""))

    def yt_headers(self) -> dict[str, str]:
        token = self.youtrack_token
        if token.lower().startswith("bearer "):
            auth = token
        else:
            auth = f"Bearer {token}"
        return {"Authorization": auth, "Accept": "application/json", "Content-Type": "application/json"}


def _parse_user_map(raw: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        login, uid = part.split(":", 1)
        out[login.strip()] = int(uid.strip())
    return out
