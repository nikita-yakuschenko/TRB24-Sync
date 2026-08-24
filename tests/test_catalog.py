from catalog import key_for_tags


def test_one_human_name():
    assert key_for_tags(["Каталог PDF"]) == "CAT"


def test_inbox():
    assert key_for_tags(["Разобрать"]) == "B24"


def test_portal_hub():
    assert key_for_tags(["смарт-процесс", "Интеграция Bitrix24 × Авангард Строй"]) == "B24"


def test_no_route():
    assert key_for_tags(["смарт-процесс"]) is None


def test_two_projects_fail():
    try:
        key_for_tags(["Каталог PDF", "Open Lines ДомКлик"])
    except ValueError:
        return
    raise AssertionError("ожидали отказ")
