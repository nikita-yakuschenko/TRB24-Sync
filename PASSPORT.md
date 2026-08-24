**YouTrack:** проект `SYNC`, название `Коннектор YouTrack × Bitrix24`  
**Владелец в трекере:** n.yakuschenko  
**Хаб:** [B24](https://tracker.avgst.ru/projects/B24) · паспорт [B24-A-1](https://tracker.avgst.ru/articles/B24-A-1) — спутник (AMS §14), бэклог не переносить в хаб.  
**Класс зрелости (AES):** Prototype → MVP (FastAPI, SQLite пар, pytest маршрута; нет прода, нет живого health внешних API, комментарии не синхронизируются)  
**Стандарты:** [AMS-1.2](https://tracker.avgst.ru/articles/ITD-A-1) · [AES-1.1](https://tracker.avgst.ru/articles/ITD-A-2) · [ADS-1.1](https://tracker.avgst.ru/articles/ITD-A-3) (ADS не применим: UI нет)

---

## Контур

| Поле | Значение |
|---|---|
| Продукт | Два насоса задач: YouTrack ↔ группа Bitrix 987 |
| YouTrack | [Коннектор YouTrack × Bitrix24](https://tracker.avgst.ru/projects/SYNC), ключ **`SYNC`** |
| Гант | [Коннектор YouTrack × Bitrix24](https://tracker.avgst.ru/gantt-charts/218-4), одна диаграмма, не дублировать |
| GitHub | [`nikita-yakuschenko/TRB24-Sync`](https://github.com/nikita-yakuschenko/TRB24-Sync), ветка `main` |
| Dokploy | проект **`sync`**, приложение **`trb24-sync`**, Dockerfile, том `sync-sqlite` → `/data` |
| URL | https://sync-trb24-sync-79a0ac-155-212-147-165.sslip.io — `GET /health` = ok |
| Bitrix | [avgstroy.bitrix24.ru](https://avgstroy.bitrix24.ru/), группа **987** avgst.io [Отдел информационных технологий] |
| MCP | `user-youtrack`, `user-b24-dev-mcp` (справка), `user-dokploy` |

Идентификаторы: `SYNC-123`. Работа только в **`SYNC`**. Задачи коннектора не зеркалятся в Bitrix (ключ в `SKIP_KEYS`). Хаб `B2B` тоже не зеркалим.

Хуки: `POST /hooks/youtrack?secret=` и `POST /hooks/bitrix?secret=` на URL выше. YouTrack: workflow **`sync-connector`** (NOTIFY TRB24-Sync) на всех продуктовых проектах, кроме `SYNC` и `B2B`. Правило `notify` шлёт хук через `postAsync` **после** коммита транзакции (4-й аргумент + `asyncFunctions`) — иначе 404 коннектора откатывает карточку. Исходник: `workflow/notify.js`. Человеческое имя `sync.module-team.ru` — после A-записи в DNS на `155.212.147.165`.

---

## Бизнес-задача

Компания ведёт работу в Bitrix. ИТ ведёт разработку в YouTrack. Заказчику нужен один список в группе 987; заявки завода на правки продуктов должны попадать в ключ продукта в трекере.

---

## Потоки

1. **YouTrack → Bitrix.** Витрина. Истина плана — трекер. В 987: заголовок `CAT-3: …`, теги «Каталог PDF» + `из YouTrack`, `XML_ID=YT:CAT-3`. Закрытие в трекере закрывает парную задачу в 987 (`tasks.task.complete`), даже если заявка пришла из Bitrix.
2. **Bitrix → YouTrack.** Заявка человека в 987. Ровно один тег = полное имя проекта YouTrack. Нет тега — тишина. Два проекта — отказ. `Разобрать` → ключ `B24`. Заголовок и описание этой заявки обратно в портал из трекера не пишем.

Эхо отсекается маркерами в описании и тегом `из YouTrack`. Удаление и комментарии в первом срезе не трогаем (AES YAGNI).

---

## Источники истины

| Данные | Master |
|---|---|
| План разработки | YouTrack ключа продукта |
| Заявки завода до принятия | задача в группе 987 |
| Пара id | SQLite коннектора |
| Словарь имён | `catalog.py` |
| Код | GitHub `nikita-yakuschenko/TRB24-Sync` |

Секреты: `.env` / Dokploy, не паспорт.

---

## Ограничения

- Входящий вебхук и исходящие события Bitrix ставит админ портала.
- Webhook YouTrack на `issueCreated` / `issueUpdated` — workflow `sync-connector` на продуктовых проектах. `SYNC` и `B2B` не вешаем.
- `BITRIX_DEFAULT_RESPONSIBLE_ID` и `USER_MAP` обязательны для зеркала в портал.
- В группе 987 заведены теги полных имён проектов плюс `из YouTrack` и `Разобрать` (служебная карточка `XML_ID=YT:SYNC-TAGS`). Свободный ввод портал не запирает — берите имя из списка.

---

## Риски

- Без словаря людей все задачи в 987 сядут на одного ответственного.
- Свободные теги в портале сломают маршрут — список закрыть.
- Ноль backup SQLite = потеря пар (карточки в системах останутся).
