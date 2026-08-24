# Коннектор YouTrack × Bitrix24

Спутник хаба [B24](https://tracker.avgst.ru/projects/B24): зеркало задач трекера в группу Bitrix **avgst.io [Отдел информационных технологий]** (`GROUP_ID` 987) и заявки из этой группы обратно в YouTrack.

Стандарты: [AMS-1.1](https://tracker.avgst.ru/articles/ITD-A-1) · [AES-1.1](https://tracker.avgst.ru/articles/ITD-A-2). UI нет, ADS не применяется. Паспорт: статья `SYNC-A-1` после заведения проекта.

План — только YouTrack `SYNC`. Секреты не коммитить.

## Потоки

1. YouTrack → Bitrix: задача трекера появляется в [группе 987](https://avgstroy.bitrix24.ru/workgroups/group/987/tasks/). В заголовке ключ (`CAT-3: …`), теги — полное имя проекта и `из YouTrack`.
2. Bitrix → YouTrack: задача в 987 без метки «из трекера» и с **ровно одним** тегом-именем проекта создаёт issue в этом ключе. Нет тега — молчим. Два имени проектов — ошибка в логе, карточку не плодим. Неясно — тег `Разобрать` (ключ `B24`).

Комментарии не синхронизируются (AES YAGNI, первый срез).

## Маршрут в портале

Люди ставят **полное имя** проекта YouTrack, не `CAT`. Словарь в `catalog.py`.

Правило: только настройка портала → `Интеграция Bitrix24 × Авангард Строй`. Есть наш микросервис → имя сервиса. Самостоятельный продукт → его имя.

## Запуск

```
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\pytest
$env:SQLITE_PATH=".\data\sync.sqlite"
.\.venv\Scripts\uvicorn main:app --port 8080
```

`GET /health` — процесс и SQLite, не живой Bitrix/YouTrack.

Вебхуки: `POST /hooks/youtrack?secret=` и `POST /hooks/bitrix?secret=`. Секрет из `WEBHOOK_SECRET`.

YouTrack: webhook app / HTTP notification на `issueCreated` и `issueUpdated`, все продуктовые проекты кроме шума, URL этого сервиса.

Bitrix: входящий вебхук (REST) в `BITRIX_WEBHOOK_URL`; исходящие события `OnTaskAdd` / `OnTaskUpdate` на `/hooks/bitrix`. Удаление не зеркалим.

`USER_MAP=n.yakuschenko:ID` — login трекера в id пользователя портала. Иначе `BITRIX_DEFAULT_RESPONSIBLE_ID`.

## Compose

Dokploy, сеть `dokploy-network` (создать, если локально: `docker network create dokploy-network`). Том SQLite. Имена панели — в паспорт после деплоя, не выдумывать.
