# План рефакторинга модуля `markdown2`

## Оценка рекомендаций из `refactoring_md2.html`

| # | Рекомендация | Оценка | Обоснование |
|---|---|---|---|
| 2.1 | Убрать `_collect_inline()` из walker | ✅ Целесообразна | Метод дублирует ответственность `InlineCollector` |
| 2.2 | Единый `handle_open()` с callback | ⚠️ Частично | Идея хорошая, но callback-паттерн усложнит отладку. Лучше явная передача контекста |
| 2.3 | Убрать циклическую зависимость | ✅ Критически важна | Это главная архитектурная проблема модуля |
| 3.1 | Прямой словарь вместо динамической сборки | ✅ Целесообразна | Упрощает понимание, устраняет дублирование множеств |
| 4.1 | Разбить PlaceholderManager на 3 класса | ⚠️ Over-engineering | Для 188 строк достаточно 2 классов: `Placeholder` (модель) + `PlaceholderManager` (логика) |
| 4.2 | Убрать `_create_closing_placeholder()` | ✅ Целесообразна | Устраняет костыль, но требует аккуратной переработки |
| 5.1 | Удалить `_fallback_align_segments()` | ❌ Опасно | Это не dead code — fallback обрабатывает реальные аномалии NLLB. Нужно вынести в отдельный файл |
| 5.2 | Выделить `SentenceSplitter` | ⚠️ Избыточно | `split_sentences` уже вынесена в `utils`, обёртка в класс не добавит ценности |
| 6.1 | Lazy initialization | ❌ Не нужна | Компоненты создаются один раз на запрос, это нормально |
| 6.2 | Config dataclass | ⚠️ Over-engineering | Достаточно читать settings в `__init__()` вместо уровня модуля |
| 7 | Новая структура модуля | ✅ Частично | Объединение мелких файлов — да. Подмодуль `placeholders/` — over-engineering |

---

## Структурная реорганизация модуля

### Проблема

На верхнем уровне `markdown2/` — россыпь из 9 файлов без понятной логики:

```
markdown2/                          # 9 файлов на верхнем уровне — каша
├── __init__.py
├── ast_walker.py              ← этап 2
├── chunker.py                 ← этап 3+5
├── translator.py              ← оркестратор (бывший markdown_translator.py)
├── node_type.py               ← общая модель
├── parser.py                  ← этап 1
├── placeholder.py             ← общая модель
├── translation_unit.py        ← общая модель
├── translation_unit_type.py   ← общая модель
├── unit_factory.py            ← общая модель
├── handlers/                  ← этап 2 (но оторван от ast_walker.py)
└── reconstructor/             ← этап 6 (уже подмодуль — хорошо)
```

### Принцип группировки

Файл принадлежит подмодулю, если он используется **только** одним этапом пайплайна. Файлы, используемые двумя и более этапами — в `models/`.

| Группа | Что входит | Логика |
|---|---|---|
| **ast_walker/** | `ast_walker.py` + `handlers/*` | Всё обслуживает обход AST. Handlers не нужны никому, кроме walker |
| **reconstructor/** | `main.py` + компоненты | Уже подмодуль. Все файлы — сборка MD |
| **models/** | `translation_unit.py`, `translation_unit_type.py`, `node_type.py`, `placeholder.py`, `unit_factory.py` | Модели данных и типы, используются на ≥2 этапах |
| Верхний уровень | `translator.py`, `parser.py`, `chunker.py` | Оркестратор, парсер, чанкер — каждый самодостаточен и мал |

### Целевая структура

```
markdown2/
├── __init__.py                        # public API: MarkdownTranslator
├── translator.py                      # оркестратор (~100 строк после рефакторинга)
├── parser.py                          # создание парсера (32 строки)
├── chunker.py                         # нарезка + merge + fallback (~300 строк)
│
├── ast_walker/                        # этап 2: обход AST
│   ├── __init__.py                    # экспорт ASTWalker
│   ├── walker.py                      # DFS-обход (бывший ast_walker.py)
│   └── handlers/
│       ├── __init__.py
│       ├── base.py                    # протокол NodeHandler
│       ├── context_block_handler.py
│       ├── structural_block_handler.py
│       ├── special_case_handler.py
│       └── inline_collector.py
│
├── reconstructor/                     # этап 6: сборка MD (уже существует)
│   ├── __init__.py
│   ├── main.py
│   ├── state_machine.py
│   ├── block_writer.py
│   ├── block_handlers.py              # CodeBlockHandler + TableHandler
│   └── placeholder_restorer.py
│
└── models/                            # общие модели данных (≥2 потребителя)
    ├── __init__.py                    # реэкспорт всех моделей
    ├── translation_unit.py            # TranslationUnit dataclass
    ├── translation_unit_type.py       # TranslationUnitType enum
    ├── node_type.py                   # маппинг типов AST-узлов
    ├── placeholder.py                 # Placeholder dataclass + PlaceholderManager
    └── unit_factory.py               # фабрика юнитов
```

### Миграция импортов

Было (относительные импорты в одном каталоге):
```python
# в ast_walker.py
from .translation_unit import TranslationUnit
from .placeholder import PlaceholderManager
from .handlers import ContextBlockHandler
```

Станет (модели — на уровень выше, walker — внутри ast_walker/):
```python
# в ast_walker/walker.py
from ..models.translation_unit import TranslationUnit
from ..models.placeholder import PlaceholderManager
from .handlers import ContextBlockHandler
```

### Почему `chunker.py` НЕ подмодуль

Chunker — один файл (~263 строки). С будущим `chunker_fallback.py` (~50 строк) — итого ~310 строк. Два файла не требуют подмодуля: лишний `__init__.py` и уровень вложенности без реальной пользы.

---

## ~~Анализ `markdown_translator.py` — пайплайн `process()`~~ ✅ РЕШЕНО

### ~~Текущее состояние пайплайна~~

| Шаг | Что делает | Где реализован | Статус |
|---|---|---|---|
| 1 | Парсинг MD → AST | `parser.py` | ✅ делегирован |
| 2 | AST → `TranslationUnit[]` | `ast_walker.py` | ✅ делегирован |
| 3 | Нарезка на чанки | `chunker.py` | ✅ делегирован |
| ~~**4**~~ | ~~**Цикл перевода чанков**~~ | ~~прямо в `process()`~~ | ✅ вынесен в `_translate_chunks()` |
| 5 | Merge переведённых чанков | `chunker.py` | ✅ делегирован |
| 6 | Реконструкция MD | `reconstructor/` | ✅ делегирован |

### ~~Выводы~~

~~**Не нужно** выносить группы шагов в подмодули — это создаст лишние абстракции для файла в 135 строк.~~

~~**Нужно:**~~
1. ~~Вынести Шаг 4 (цикл перевода) в приватный метод `_translate_chunks()`~~ ✅ выполнено в Фазе 0b
2. ~~Убрать `max_input_tokens = settings.max_input_tokens` с уровня модуля~~ ✅ выполнено в Фазе 0b: заменено на параметр `max_tokens` в конструкторе

**Результат:** `process()` теперь компактный декларативный список шагов, каждый шаг — один вызов.

---

## Ключевые проблемы (по приоритету)

1. **Циклические зависимости** — handler-ы вызывают приватные методы `ASTWalker`, `InlineCollector` мутирует `_context_stack` в `ContextBlockHandler`
2. **Дублирование** — создание закрывающих маркеров в 4+ местах, `_PAIRED_STRUCTURAL_BLOCKS` определено дважды
3. **God Objects** — `reconstructor/main.py` (357 строк), `context_block_handler.py` (241 строка)
4. ~~**Отсутствие `__init__.py`** в корне `markdown2/`~~ ✅ исправлено (Фаза 0)
5. ~~**Баг в логировании** — `markdown_translator.py` логирует пустую строку~~ ✅ исправлено (Фаза 0)
6. ~~**Неправильный импорт** — `reconstructor/main.py` использует `from src.mt_server.config`~~ ✅ исправлено (Фаза 0)
7. ~~**Сырая реализация Шага 4** в `process()` — цикл перевода чанков inline~~ ✅ исправлено (Фаза 0b)
8. ~~**Глобальная переменная** `max_input_tokens` на уровне модуля~~ ✅ исправлено (Фаза 0b)

---

## План рефакторинга

### ~~Фаза 0: Подготовительная (безопасная)~~ ✅ ВЫПОЛНЕНА

- ~~0.1. Добавить `__init__.py` в `markdown2/`~~ ✅
- ~~0.2. Исправить баг в логировании `markdown_translator.py`~~ ✅
- ~~0.3. Исправить неправильный импорт в `reconstructor/main.py`~~ ✅
- ~~0.4. Удалить отладочный метод `_blocks_qty()` из `ast_walker.py`~~ ✅

---

### ~~Фаза 0b: Очистка оркестратора~~ ✅ ВЫПОЛНЕНА

> ~~Цель: сделать `process()` компактным и симметричным, убрать глобальное состояние модуля~~

- ~~0b.1. Вынести цикл перевода чанков (Шаг 4) в метод `_translate_chunks()`~~ ✅
- ~~0b.2. Убрать `max_input_tokens` с уровня модуля~~ ✅ заменено на параметр `max_tokens` в конструкторе
- ~~0b.3. Переименовать файл: `markdown_translator.py` → `translator.py`~~ ✅
- Все импорты обновлены: `handlers.py`, `__init__.py`, `conftest.py`, `test_translation_service.py` ✅
- Патчи `max_input_tokens` в тестах заменены на прямую передачу `max_tokens=...` ✅

---

### ~~Фаза 0c: Структурная реорганизация~~ ✅ ВЫПОЛНЕНА

> ~~Цель: разложить файлы по подмодулям согласно принадлежности к этапам пайплайна~~

- ~~0c.1. Создать `ast_walker/` подмодуль~~ ✅
  - ~~`ast_walker.py` → `ast_walker/walker.py`~~ ✅
  - ~~`handlers/` → `ast_walker/handlers/`~~ ✅
  - ~~`ast_walker/__init__.py` с экспортом `ASTWalker`~~ ✅
- ~~0c.2. Создать `models/` подмодуль~~ ✅
  - ~~5 файлов перенесены: `translation_unit_type`, `translation_unit`, `node_type`, `unit_factory`, `placeholder`~~ ✅
  - ~~`models/__init__.py` с реэкспортом всех моделей~~ ✅
- ~~0c.3. Обновить импорты по всему модулю~~ ✅
  - ~~Все внутренние импорты (walker, handlers, reconstructor, translator, chunker)~~ ✅
  - ~~Все тестовые импорты (8 файлов)~~ ✅
- Тесты: **86 passed** (62 markdown2 + 24 service) ✅
- Линтер: **All checks passed!** ✅

---

### Фаза 1: Устранение циклических зависимостей

> Цель: разорвать двунаправленные связи между Walker и Handler-ами

**1.1. Определить протокол `NodeHandler`** в `ast_walker/handlers/base.py`

```python
class NodeHandler(Protocol):
    def handle_node(
        self, node: SyntaxTreeNode, parent_id: str, index: int
    ) -> bool: ...
```

**1.2. Убрать обратную ссылку handler-ов на `ASTWalker`**

- `ASTWalker._traverse()` → передать как callable-параметр `traverse_fn`
- `ASTWalker._generate_node_id()` → вынести в отдельный `IdGenerator` (простой класс-счётчик), инжектить в handler-ы
- Результат (`units`) — накапливать через callback `append_unit(unit)`, а не через `walker.units`

**1.3. Убрать мутацию `_context_stack` из `InlineCollector`**

- `ContextBlockHandler` передаёт в `InlineCollector` текущий контекст (unit + placeholder_manager) явно
- `InlineCollector` возвращает результат через return value
- Закрытие контекста — ответственность `ContextBlockHandler`

**1.4. Убрать `_collect_inline()` из `ASTWalker`**

Метод переносится в `InlineCollector` как приватный. Walker делегирует через dispatch.

---

### Фаза 2: Консолидация дублирующегося кода

> Цель: устранить 4+ мест создания закрывающих маркеров

**2.1. Создать фабрику закрывающих маркеров в `unit_factory.py`**

Вынести логику `create_close_marker()` из `ContextBlockHandler._handle_close()`, `InlineCollector.collect()`, `StructuralBlockHandler._handle_open()` в единый метод.

**2.2. Устранить дублирование `_PAIRED_STRUCTURAL_BLOCKS`**

- Перенести определение в `models/node_type.py` как `_PAIRED_STRUCTURAL_TYPES`
- `StructuralBlockHandler` использует `get_unit_type()` вместо локального множества

**2.3. Вынести табличные методы из `BlockWriter`**

- `contains_pipe()`, `count_table_columns()`, `get_last_pipe_line()` → в `TableHandler`
- `BlockWriter` остаётся чистым writer-ом

---

### Фаза 3: Упрощение `node_type.py`

> Цель: читаемость и устранение дублирования

**3.1. Заменить динамическую сборку на плоский словарь**

Вместо множеств и циклов — один явный словарь `_NODE_TYPE_MAP` с комментариями-группами.

**3.2. Удалить промежуточные множества**

`_STRUCTURAL_BLOCKS`, `_PARSED_STRUCTURAL_BLOCKS` — удалить.

---

### Фаза 4: Упрощение мелких модулей

> Цель: уменьшить количество файлов без потери функциональности

**4.1. Объединить `translation_unit_type.py` + `translation_unit.py` + `unit_factory.py` → один файл `models/translation_unit.py`**

- `TranslationUnitType` (enum, 16 строк)
- `TranslationUnit` (dataclass, 41 строка)
- Фабричные функции (бывшие методы `UnitFactory`, переделать в обычные функции)
- Итого ~80 строк вместо 3 файлов

**4.2. Поглотить `SpecialCaseHandler` в `StructuralBlockHandler`**

`SpecialCaseHandler` обрабатывает единственный тип `front_matter`.

**4.3. Объединить `CodeBlockHandler` + `TableHandler` → `reconstructor/block_handlers.py`**

Оба небольшие (64 + 97 = 161 строка), логически связаны.

---

### Фаза 5: Рефакторинг `reconstructor/main.py`

> Цель: уменьшить God Object (357 строк)

**5.1. Убрать двойной путь обработки таблиц**

`th/td` обрабатывается и в `_handle_context_block()`, и в `_handle_structural_marker()`. Оставить один путь — через `TableHandler`.

**5.2. Вынести routing-логику из `_handle_structural_marker()`**

Создать `_dispatch_structural(unit)` — простой dispatch по `base_type`.

**5.3. Удалить избыточные debug-логи**

Убрать `logger.debug` с `buffer[-3:]`, `buffer[-5:]`.

**5.4. Убрать прямую мутацию `_buffer` в `BlockWriter`**

Добавить метод `BlockWriter.trim_trailing_newline()` вместо доступа к приватному полю.

**5.5. Компилировать regex на уровне модуля в `placeholder_restorer.py`**

Вынести `paired_regex` и `atomic_regex` на уровень модуля. Добавить `max_iterations` в `while old_text != text`.

---

### Фаза 6: Улучшение `PlaceholderManager`

> Цель: чёткое разделение ответственности

**6.1. Разделить модель и логику**

- `Placeholder` — frozen dataclass (без методов, чистые данные)
- `PlaceholderManager` — логика создания, ID, стека парных тегов

**6.2. Исправить хрупкий стек парных тегов**

Использовать `node_type` (а не префикс) как ключ в `_open_tags_stacks`.

**6.3. Унифицировать тип `original_markup`**

Вместо `Union[str, Dict]` — всегда использовать `Dict[str, Any]`.

---

### Фаза 7: Оптимизация `chunker.py`

> Цель: чистая структура без потери функциональности

**7.1. Вынести `_fallback_align_segments()` в отдельный файл**

Создать `chunker_fallback.py` — fallback-алгоритм для аномалий NLLB.

---

## Итоговая целевая структура

```
markdown2/
├── __init__.py                        # public API: MarkdownTranslator
├── translator.py                      # оркестратор (~100 строк)
├── parser.py                          # парсер (32 строки)
├── chunker.py                         # нарезка + merge (~300 строк)
│
├── ast_walker/                        # обход AST
│   ├── __init__.py
│   ├── walker.py                      # DFS-обход (~80 строк)
│   └── handlers/
│       ├── __init__.py
│       ├── base.py                    # протокол NodeHandler
│       ├── context_block_handler.py   # (~180 строк)
│       ├── structural_block_handler.py # + front_matter (~200 строк)
│       └── inline_collector.py        # (~120 строк)
│
├── reconstructor/                     # сборка MD
│   ├── __init__.py
│   ├── main.py                        # (~250 строк)
│   ├── state_machine.py               # (~150 строк)
│   ├── block_writer.py                # (~80 строк)
│   ├── block_handlers.py              # code + table (~140 строк)
│   └── placeholder_restorer.py        # (~230 строк)
│
└── models/                            # общие модели данных
    ├── __init__.py
    ├── translation_unit.py            # TranslationUnit + TranslationUnitType + фабрика (~80 строк)
    ├── node_type.py                   # плоский словарь (~50 строк)
    └── placeholder.py                 # Placeholder + PlaceholderManager (~120 строк)
```

**Итого: ~1 500 строк, 18 файлов, 4 подмодуля** (было ~2 743 строки, 22 файла, 2 подмодуля)

---

## Порядок выполнения

| Приоритет | Фаза | Риск | Зависимости | Статус |
|---|---|---|---|---|
| 1 | Фаза 0 — Подготовительная | Нулевой | Нет | ✅ Выполнена |
| 2 | Фаза 0b — Очистка оркестратора | Нулевой | Нет | ✅ Выполнена |
| 3 | Фаза 0c — Структурная реорганизация | Низкий | Фаза 0b | Ожидает |
| 4 | Фаза 3 — Упрощение `node_type.py` | Низкий | Фаза 0c | Ожидает |
| 5 | Фаза 1 — Устранение циклических зависимостей | Средний | Фаза 0c | Ожидает |
| 6 | Фаза 2 — Консолидация дублирования | Средний | Фаза 1 | Ожидает |
| 7 | Фаза 4 — Упрощение мелких модулей | Низкий | Фаза 1 | Ожидает |
| 8 | Фаза 5 — Рефакторинг reconstructor | Средний | Фаза 2 | Ожидает |
| 9 | Фаза 6 — Улучшение PlaceholderManager | Низкий | Фаза 4 | Ожидает |
| 10 | Фаза 7 — Оптимизация Chunker | Низкий | Фаза 4 | Ожидает |

**После каждой фазы** — запуск `uv run pytest tests/markdown2/ -v -s` + `uv run ruff check .`

---

## Критерии завершения

- [ ] Все тесты `tests/markdown2/` проходят без изменений тестовых сценариев
- [ ] Нет циклических зависимостей между модулями
- [ ] Нет файлов > 250 строк
- [ ] `ruff check` без предупреждений
- [x] Все импорты используют `from mt_server...` (не `from src.mt_server...`) ✅
- [x] `__init__.py` есть в каждом пакете ✅
