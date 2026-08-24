**YouTrack:** проект `SYNC`, название `Коннектор YouTrack × Bitrix24`  
**Владелец в трекере:** n.yakuschenko  
**Хаб:** [B24](https://tracker.avgst.ru/projects/B24) · паспорт [B24-A-1](https://tracker.avgst.ru/articles/B24-A-1) — спутник (AMS §14), бэклог не переносить в хаб.  
**Класс зрелости (AES):** Prototype → MVP (FastAPI, SQLite пар, pytest маршрута; нет прода, нет живого health внешних API, комментарии не синхронизируются)  
**Стандарты:** [AMS-1.1](https://tracker.avgst.ru/articles/ITD-A-1) · [AES-1.1](https://tracker.avgst.ru/articles/ITD-A-2) · [ADS-1.1](https://tracker.avgst.ru/articles/ITD-A-3) (ADS не применим: UI нет)

---

## Контур

| Поле | Значение |
|---|---|
| Продукт | Два насоса задач: YouTrack ↔ группа Bitrix 987 |
| YouTrack | [Коннектор YouTrack × Bitrix24](https://tracker.avgst.ru/projects/SYNC), ключ **`SYNC`** |
| Гант | одна диаграмма на `SYNC`; пока нет |
| GitHub | TBD (этот репозиторий, remote ещё не заведён) |
| Dokploy | TBD после деплоя; compose `docker-compose.yml`, порт **8080** |
| Bitrix | [avgstroy.bitrix24.ru](https://avgstroy.bitrix24.ru/), группа **987** avgst.io [Отдел информационных технологий] |
| MCP | `user-youtrack`, `user-b24-dev-mcp` (справка), `user-dokploy` после деплоя |

Идентификаторы: `SYNC-123`. Работа только в **`SYNC`**. Задачи коннектора не зеркалятся в Bitrix (ключ в `SKIP_KEYS`).

---

## Бизнес-задача

Компания ведёт работу в Bitrix. ИТ ведёт разработку в YouTrack. Заказчику нужен один список в группе 987; заявки завода на правки продуктов должны попадать в ключ продукта в трекере.

---

## Потоки

1. **YouTrack → Bitrix.** Витрина. Истина плана — трекер. В 987: заголовок `CAT-3: …`, теги «Каталог PDF» + `из YouTrack`, `XML_ID=YT:CAT-3`.
2. **Bitrix → YouTrack.** Заявка человека в 987. Ровно один тег = полное имя проекта YouTrack. Нет тега — тишина. Два проекта — отказ. `Разобрать` → ключ `B24`.

Эхо отсекается маркерами в описании и тегом `из YouTrack`. Удаление и комментарии в первом срезе не трогаем (AES YAGNI).

---

## Источники истины

| Данные | Master |
|---|---|
| План разработки | YouTrack ключа продукта |
| Заявки завода до принятия | задача в группе 987 |
| Пара id | SQLite коннектора |
| Словарь имён | `catalog.py` |

Секреты: `.env` / Dokploy, не паспорт.

---

## Ограничения

- Входящий вебхук и исходящие события Bitrix ставит админ портала.
- Webhook YouTrack на `issueCreated` / `issueUpdated` — в UI трекера.
- `BITRIX_DEFAULT_RESPONSIBLE_ID` и `USER_MAP` обязательны для зеркала в портал.
- Поле-список в Bitrix надёжнее тегов; первый срез читает теги.

---

## Риски

- Без словаря людей все задачи в 987 сядут на одного ответственного.
- Свободные теги в портале сломают маршрут — список закрыть.
- Ноль backup SQLite = потеря пар (карточки в системах останутся).
