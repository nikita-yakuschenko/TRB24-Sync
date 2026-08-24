# Служебные маркеры в описании, чтобы не поймать эхо вебхука.

import re

YT_MARK = re.compile(r"<!--\s*sync:youtrack:([A-Z0-9]+-\d+)\s*-->")
BX_MARK = re.compile(r"<!--\s*sync:bitrix:(\d+)\s*-->")


def youtrack_marker(issue_id: str) -> str:
    return f"<!-- sync:youtrack:{issue_id} -->"


def bitrix_marker(task_id: int | str) -> str:
    return f"<!-- sync:bitrix:{task_id} -->"


def parse_youtrack_id(text: str | None) -> str | None:
    if not text:
        return None
    found = YT_MARK.search(text)
    return found.group(1) if found else None


def parse_bitrix_id(text: str | None) -> str | None:
    if not text:
        return None
    found = BX_MARK.search(text)
    return found.group(1) if found else None
