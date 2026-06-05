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
9. ~~**Россыпь файлов** на верхнем уровне (9 файлов без логики группировки)~~ ✅ исправлено (Фаза 0c)
10. ~~**Плейсхолдеры прилипают к тексту** — NLLB воспринимает `__B_O_1__текст__B_C_1__` как единое слово~~ ✅ исправлено (пробелы вокруг плейсхолдеров)
11. ~~**Хардкод разделителя** `REC_SEPARATOR = " __S__ "` в `chunker.py` без связи со словарём плейсхолдеров~~ ✅ исправлено (`SEGMENT_SEPARATOR` в `placeholder_codes.py`)

---

## Текущая структура модуля (после Фазы 0c)

```
markdown2/
├── __init__.py                        # public API: MarkdownTranslator
├── translator.py                  (140) — оркестратор, ✅ очищен
├── parser.py                       (32) — ✅ без проблем
├── chunker.py                     (263) — SRP нарушен: упаковка + merge + fallback
│
├── ast_walker/                        # этап 2: обход AST
│   ├── __init__.py                    # экспорт ASTWalker
│   ├── walker.py                  (129) — God Object, tight coupling с handlers
│   └── handlers/
│       ├── __init__.py
│       ├── context_block_handler.py (241) — самый большой handler, дублирование
│       ├── structural_block_handler.py (182) — дублирует _PARSED_STRUCTURAL_BLOCKS
│       ├── special_case_handler.py   (69) — over-engineering для одного типа
│       └── inline_collector.py      (138) — лезет в ContextBlockHandler
│
├── reconstructor/                     # этап 6: сборка MD
│   ├── __init__.py
│   ├── main.py                  (357) — God Object, два пути для таблиц
│   ├── state_machine.py         (170) — getter с побочными эффектами
│   ├── block_writer.py          (105) — табличные методы не по адресу
│   ├── code_block_handler.py     (64) — дублирование if/else
│   ├── placeholder_restorer.py  (275) — O(n*m) нормализация, regex в методах
│   └── table_handler.py          (97) — мёртвые методы, фиктивные блоки в стеке
│
└── models/                            # общие модели данных
    ├── __init__.py                    # реэкспорт всех моделей
    ├── translation_unit_type.py  (16) — ✅ без проблем
    ├── translation_unit.py       (41) — данные смешаны с состоянием pipeline
    ├── node_type.py              (116) — дублирование множеств, сложная инициализация
    ├── unit_factory.py            (91) — namespace class (все методы статические)
    └── placeholder.py            (188) — 3 ответственности в одном классе
```

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

### ~~Фаза 0d: Рефакторинг системы плейсхолдеров~~ ✅ ВЫПОЛНЕНА

> ~~**Критично для production**: текущий формат `{lnk_1}` воспринимается NLLB как слово для перевода.~~

**Реализовано:**

- ~~0d.1. Создать `models/placeholder_codes.py`~~ ✅
  - Словари `PAIRED_CODES`, `SINGLE_TRANSLATE_CODES`, `PROTECT_CODES`
  - Функции `get_code()`, `format_placeholder()`, `is_paired_type()`
  - Полный охват всех типов узлов из markdown-it-py и плагинов

- ~~0d.2. Новый формат плейсхолдеров~~ ✅
  - Старый: `{lnk_1}`, `{/lnk_1}`, `{s_1}`, `{code_1}`
  - Новый: `__L_O_1__`, `__L_C_1__`, `__B_O_1__`, `__C_1__`
  - Dunder-формат явно не является словом для NLLB

- ~~0d.3. Обновить `Placeholder` dataclass~~ ✅
  - Добавлены поля `has_leading_space` и `has_trailing_space`
  - Позволяет сохранять контекст пробелов для корректного восстановления

- ~~0d.4. Обновить `PlaceholderManager.create_placeholder()`~~ ✅
  - Использует `get_code()` из `placeholder_codes.py`
  - Генерирует маски в dunder-формате
  - Принимает параметры `has_leading_space` / `has_trailing_space`

- ~~0d.5. Обновить `PlaceholderRestorer`~~ ✅
  - Новые regex для `__X_Y_N__` формата
  - Умная нормализация текста с учетом пунктуации
  - Корректное восстановление парных и атомарных тегов

- ~~0d.6. Обновить тесты плейсхолдеров~~ ✅
  - `test_markdown_placeholder_manager.py` - 10 тестов
  - `test_markdown_reconstructor.py` - 2 теста
  - `test_markdown_ast_walker.py` - 1 тест
  - `test_markdown_elements.py` - 5 тестов
  - `test_markdown_integration.py` - 1 тест
  - `conftest.py` - `integration_translation_dict`

**Результаты:**
- Все 65 тестов markdown2 проходят ✅
- Все 24 теста service проходят ✅
- Линтер: All checks passed! ✅

**Преимущества**:
- Тесты импортируют тот же словарь — нет дублирования
- Легко расширять (одна строка на новый тип)

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
| 3 | Фаза 0c — Структурная реорганизация | Низкий | Фаза 0b | ✅ Выполнена |
| 4 | **Фаза 0d — Рефакторинг плейсхолдеров** | **Средний** | **Фаза 0c** | ✅ Выполнена |
| 4a | **Пробелы вокруг плейсхолдеров + SEGMENT_SEPARATOR** | **Низкий** | **Фаза 0d** | ✅ Выполнена |
| 5 | Фаза 3 — Упрощение `node_type.py` | Низкий | Фаза 0c | Ожидает |
| 6 | Фаза 1 — Устранение циклических зависимостей | Средний | Фаза 0c | Ожидает |
| 7 | Фаза 2 — Консолидация дублирования | Средний | Фаза 1 | Ожидает |
| 8 | Фаза 4 — Упрощение мелких модулей | Низкий | Фаза 1 | Ожидает |
| 9 | Фаза 5 — Рефакторинг reconstructor | Средний | Фаза 2 | Ожидает |
| 10 | Фаза 6 — Улучшение PlaceholderManager | Низкий | Фаза 0d | Ожидает |
| 11 | Фаза 7 — Оптимизация Chunker | Низкий | Фаза 4 | Ожидает |

**После каждой фазы** — запуск `uv run pytest tests/markdown2/ -v -s` + `uv run ruff check .`

---

## Критерии завершения

- [ ] Все тесты `tests/markdown2/` проходят без изменений тестовых сценариев
- [ ] Нет циклических зависимостей между модулями
- [ ] Нет файлов > 250 строк
- [ ] `ruff check` без предупреждений
- [ ] Плейсхолдеры используют dunder-формат (`__X_Y_N__`) и не воспринимаются NLLB как слова ✅ (Фаза 0d)
- [ ] Словарь кодов плейсхолдеров вынесен в `models/placeholder_codes.py` ✅ (Фаза 0d)
- [ ] Контекст пробелов сохраняется в `Placeholder` и учитывается при реконструкции ✅ (Фаза 0d)
- [x] Все плейсхолдеры в `extracted_text` отделены пробелами от окружаающего текста ✅ (`InlineCollector._append_tag`)
- [x] `SEGMENT_SEPARATOR` централизован в `placeholder_codes.py`, используется в `chunker.py` и тестах ✅
- [x] `normalize_text()` убирает пробел между закрывающим плейсхолдером и пунктуацией ✅
- [x] Все импорты используют `from mt_server...` (не `from src.mt_server...`) ✅
- [x] `__init__.py` есть в каждом пакете ✅
- [x] Файлы сгруппированы по подмодулям согласно этапам пайплайна ✅ (Фаза 0c)
