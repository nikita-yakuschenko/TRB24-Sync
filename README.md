# Коннектор YouTrack × Bitrix24

Спутник хаба [B24](https://tracker.avgst.ru/projects/B24): зеркало задач трекера в группу Bitrix **avgst.io [Отдел информационных технологий]** (`GROUP_ID` 987) и заявки из этой группы обратно в YouTrack.

Стандарты: [AMS-1.2](https://tracker.avgst.ru/articles/ITD-A-1) · [AES-1.1](https://tracker.avgst.ru/articles/ITD-A-2). UI нет, ADS не применяется. Паспорт: [SYNC-A-1](https://tracker.avgst.ru/articles/SYNC-A-1). Git: [nikita-yakuschenko/TRB24-Sync](https://github.com/nikita-yakuschenko/TRB24-Sync), ветка `main`.

План — только YouTrack `SYNC`. Секреты не коммитить.

## Потоки

1. YouTrack → Bitrix: задача трекера появляется в [группе 987](https://avgstroy.bitrix24.ru/workgroups/group/987/tasks/). В заголовке ключ (`CAT-3: …`), теги — полное имя проекта и `из YouTrack`. Закрытие в трекере закрывает парную карточку в 987.
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

YouTrack: webhook app / HTTP notification **или** workflow `sync-connector` (NOTIFY TRB24-Sync) на продуктовых проектах, URL этого сервиса. `SYNC` и `B2B` не вешаем. В `notify` обязателен 4-й аргумент `postAsync` (хук после коммита), иначе создание задачи откатывается. Исходник: `workflow/notify.js`.

Bitrix: входящий вебхук (REST) в `BITRIX_WEBHOOK_URL`; исходящие события `OnTaskAdd` / `OnTaskUpdate` на `/hooks/bitrix`. Удаление не зеркалим.

`USER_MAP=n.yakuschenko:ID` — login трекера в id пользователя портала. Иначе `BITRIX_DEFAULT_RESPONSIBLE_ID`.

## Деплой

Dokploy: проект `sync`, приложение `trb24-sync`, Dockerfile, том `sync-sqlite` → `/data`. Живой URL — в [SYNC-A-1](https://tracker.avgst.ru/articles/SYNC-A-1). Локально: сеть `dokploy-network` (`docker network create dokploy-network`).
