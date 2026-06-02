# QWEN.md — Контекст проекта для Qwen Code

## Проект

Система машинного перевода (machine translation). Работает полностью on-premises, без облачных сервисов. Многопользовательская, web.

## Стек

- **Язык:** Python 3.12
- **Менеджер пакетов:** `uv` (в т.ч. внутри Docker-контейнеров)
- **Web-фреймворк:** FastAPI + Uvicorn
- **ML:** HuggingFace Transformers, PyTorch, Accelerate
- **Модель перевода:** `facebook/nllb-200-distilled-600M`
- **Markdown-парсинг:** markdown-it-py, mdit-py-plugins
- **Линтер/форматтер:** Ruff
- **Тесты:** pytest
- **Контейнеризация:** Docker, docker-compose (Nvidia GPU)

## Структура

```
/opt/mt/
├── nllb-server/
│   ├── src/
│   │   ├── mt_server/          # Основной код сервера
│   │   │   ├── main.py         # Точка входа FastAPI
│   │   │   ├── config.py       # Конфигурация
│   │   │   ├── engine.py       # ML-движок (загрузка модели, инференс)
│   │   │   ├── handlers.py     # HTTP-обработчики
│   │   │   ├── translation_service.py  # Сервис перевода
│   │   │   ├── plain_text_translator.py # Перевод plain text
│   │   │   ├── languages.py    # Список языков
│   │   │   ├── markdown2/      # Подсистема перевода Markdown (текущая работа)
│   │   │   │   ├── parser.py          # Парсинг MD в AST
│   │   │   │   ├── ast_walker.py      # Обход дерева
│   │   │   │   ├── chunker.py         # Разбивка на чанки
│   │   │   │   ├── markdown_translator.py  # Оркестратор
│   │   │   │   ├── handlers/          # Обработчики узлов AST
│   │   │   │   └── reconstructor/     # Сборка MD обратно из перевода
│   │   │   └── ...
│   │   └── mt_client/          # Клиент (пусто, заглушка)
│   ├── tests/                  # Тесты, зеркалят структуру src
│   │   ├── markdown2/
│   │   ├── plain_text_translator/
│   │   ├── api/
│   │   ├── languages/
│   │   └── ...
│   ├── pyproject.toml
│   ├── Dockerfile / Dockerfile.dev
│   └── languages.json
├── models/                     # Локальные ML-модели (примонтированы в контейнер)
├── cache/                      # Кэш HuggingFace
├── docker-compose.yml          # Прод
└── docker-compose.dev.yml      # Разработка
```

## Команды

Все команды выполняются из `/opt/mt/nllb-server/`:

```bash
# Установка зависимостей
uv sync

# Запуск тестов
uv run pytest

# Запуск тестов с подробным выводом
uv run pytest -v -s

# Конкретный тест-файл
uv run pytest tests/markdown2/

# Линтинг
uv run ruff check .

# Автофикс линтера
uv run ruff check --fix .

# Запуск сервера (dev, без Docker)
uv run uvicorn mt_server.main:app --reload --host 0.0.0.0 --port 8000

# Запуск в Docker (прод)
docker compose up --build -d
```

## Соглашения

- Тесты лежат в `tests/`, структура зеркалит `src/mt_server/`
- `pythonpath` для pytest настроен на `src` (см. `pyproject.toml`)
- Используй `uv run` вместо прямого вызова python/pytest
- Код на русском в комментариях и commit messages — это нормально
- Ветка по умолчанию: `markdown-2` (текущая работа — подсистема Markdown-перевода)

## API Endpoints

| Метод | Путь          | Описание                        |
|-------|---------------|---------------------------------|
| POST  | `/translate`  | Перевести текст (plain или MD)  |
| GET   | `/health`     | Состояние сервера, GPU, модель  |
| GET   | `/languages`  | Список доступных языков         |

## Текущая работа

Ветка `markdown-2` — разработка подсистемы сохранения Markdown-форматирования при переводе. Пайплайн: парсинг MD → AST → извлечение текста → перевод → реконструкция MD.
