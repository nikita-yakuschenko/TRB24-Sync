from bitrix_events import task_id_from_event
from markers import bitrix_marker, parse_bitrix_id, parse_youtrack_id, youtrack_marker


def test_markers():
    text = youtrack_marker("CAT-3") + "\nhello"
    assert parse_youtrack_id(text) == "CAT-3"
    assert parse_bitrix_id(bitrix_marker(99)) == "99"


def test_json_event():
    payload = {"event": "ONTASKADD", "data": {"FIELDS_AFTER": {"ID": 15}}}
    assert task_id_from_event(payload) == "15"


def test_ignore_other_event():
    assert task_id_from_event({"event": "ONCRMDEALADD", "data": {"FIELDS_AFTER": {"ID": 1}}}) is None
