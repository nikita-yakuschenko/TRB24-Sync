# Словарь имён Bitrix → ключ YouTrack. Люди в портале видят имя, не CAT.

NAME_TO_KEY = {
    "Каталог PDF": "CAT",
    "Open Lines ДомКлик": "COL",
    "Сокращатель ссылок": "GO",
    "Roistat Metrika": "ROI",
    "Интеграция Bitrix24 × Авангард Строй": "B24",
    "MCP 1С УПП": "MCP",
    "SmartCut 2": "SC2",
    "ASL Coldbase": "ASL",
    "AVGST Supply Bot": "BOT",
    "module.team сайт": "SITE",
    "Личный кабинет": "LK",
    "API Docs": "DOCS",
    "Supabase": "SB",
    "Bitwarden": "BW",
    "Трекер ИТ": "TRK",
    "Общий проект отдела": "ITD",
    "Разобрать": "B24",
}

KEY_TO_NAME = {key: name for name, key in NAME_TO_KEY.items() if name != "Разобрать"}
KEY_TO_NAME["B24"] = "Интеграция Bitrix24 × Авангард Строй"

INBOX_NAME = "Разобрать"
FROM_TRACKER_TAG = "из YouTrack"
SKIP_KEYS = {"SYNC"}


def key_for_tags(tags: list[str]) -> str | None:
    """Ровно один маршрутный тег. Два — отказ. Ноль — нет маршрута."""
    hits = []
    for tag in tags:
        name = (tag or "").strip()
        if name in NAME_TO_KEY:
            hits.append(NAME_TO_KEY[name])
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    if len(unique) > 1:
        raise ValueError("несколько проектов в тегах: " + ", ".join(unique))
    return None
