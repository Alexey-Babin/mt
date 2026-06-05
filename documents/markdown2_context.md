# Модуль markdown2: Контекст для разработки

## Назначение

Модуль `markdown2` реализует систему перевода Markdown-документов с сохранением форматирования. Он является частью системы машинного перевода и работает поверх NLLB-модели (`facebook/nllb-200-distilled-600M`).

**Ключевая задача:** перевести текст документа, сохранив при этом всю Markdown-разметку (заголовки, списки, таблицы, код, ссылки, форматирование и т.д.).

## Архитектура

### Общая схема работы

```
Исходный Markdown
    ↓
[parser.py] → markdown-it-py → токены
    ↓
[ast_walker/walker.py] → обход AST → список TranslationUnit
    ↓
[chunker.py] → разбиение на чанки по токен-лимитам
    ↓
[translator.py] → перевод каждого чанка через NLLB
    ↓
[chunker.py] → merge переведенных чанков обратно в TranslationUnit
    ↓
[reconstructor/] → сборка финального Markdown
    ↓
Переведенный Markdown
```

### Структура модуля

```
markdown2/
├── __init__.py                    # Точка входа, экспорт MarkdownTranslator
├── parser.py                      # Создание парсера markdown-it-py
├── translator.py                  # Оркестратор всего пайплайна
├── chunker.py                     # Разбиение и merge чанков
│
├── models/                        # Общие модели данных
│   ├── translation_unit.py        # TranslationUnit - основная единица перевода
│   ├── translation_unit_type.py   # Enum типов (CONTEXT_BLOCK, INLINE_TRANSLATE, etc.)
│   ├── placeholder.py             # Placeholder - защита inline-элементов
│   ├── placeholder_codes.py       # Словарь кодов для плейсхолдеров
│   ├── node_type.py               # Маппинг AST-узлов на TranslationUnitType
│   └── unit_factory.py            # Фабрика создания TranslationUnit
│
├── ast_walker/                    # Обход AST-дерева
│   ├── walker.py                  # ASTWalker - основной walker
│   └── handlers/                  # Обработчики разных типов узлов
│       ├── context_block_handler.py       # Абзацы, заголовки, ячейки таблиц
│       ├── structural_block_handler.py    # Списки, цитаты, код
│       ├── inline_collector.py            # Сбор inline-элементов
│       └── special_case_handler.py        # Front matter и прочие особые случаи
│
└── reconstructor/                 # Сборка финального Markdown
    ├── main.py                    # MarkdownReconstructor - оркестратор сборки
    ├── state_machine.py           # Стек блоков и префиксов
    ├── block_writer.py            # Запись текста с учетом префиксов
    ├── placeholder_restorer.py    # Восстановление плейсхолдеров
    ├── code_block_handler.py      # Обработка блоков кода
    └── table_handler.py           # Обработка таблиц
```

## Ключевые концепции

### TranslationUnit

Основная единица работы модуля. Представляет собой фрагмент Markdown-документа с метаданными:

```python
@dataclass
class TranslationUnit:
    id: str                      # Уникальный идентификатор
    node_type: str               # Тип AST-узла (например, "paragraph")
    unit_type: TranslationUnitType  # Категория обработки
    original_text: str           # Исходный текст (до плейсхолдеров)
    extracted_text: str          # Текст с плейсхолдерами (для перевода)
    translated_text: str         # Переведенный текст
    need_translation: bool       # Флаг необходимости перевода
    placeholders: List[Placeholder]  # Список плейсхолдеров
    # ... другие поля
```

**Типы TranslationUnit:**
- `CONTEXT_BLOCK` - блоки контекста (абзацы, заголовки, ячейки таблиц) - требуют перевода
- `INLINE_TRANSLATE` - inline-элементы, которые нужно перевести (ссылки, изображения)
- `INLINE_PROTECT` - inline-элементы, которые нужно защитить от перевода (код, формулы)
- `STRUCTURAL_IGNORE` - структурные элементы (списки, цитаты) - не переводятся
- `SPECIAL_CASE` - особые случаи (front matter)

### Placeholder система

**Проблема:** NLLB пытается перевести Markdown-разметку как обычный текст, что ломает структуру документа.

**Решение:** Замена inline-элементов на плейсхолдеры перед отправкой в NLLB, с последующим восстановлением после перевода.

**Формат плейсхолдеров (dunder-стиль):**
- Парные теги: `__X_O_N__` ... `__X_C_N__` (например, `__B_O_1__` для `<strong>`)
- Одиночные теги: `__X_N__` (например, `__C_1__` для `` `code` ``)

**Ключевое правило: все плейсхолдеры отделены пробелами от окружаающего текста.**
Это гарантирует, что NLLB воспринимает каждый плейсхолдер как отдельный токен, а не как часть слова. Пробелы добавляются на этапе AST-walk в `InlineCollector._append_tag()`, а при реконструкции `PlaceholderRestorer.normalize_text()` убирает артефактные пробелы между плейсхолдерами и пунктуацией.

**Пример:**
```
Исходный:  Это **важный** текст с `кодом`.
С плейсхолдерами: Это __B_O_1__ важный __B_C_1__  текст с __C_1__ .
После перевода: This __B_O_1__ important __B_C_1__  text with __C_1__ .
Восстановлено: This **important** text with `code`.
```

**Словарь кодов** (`placeholder_codes.py`):
```python
PAIRED_CODES = {
    "strong": "B",    # Bold
    "em": "I",        # Italic
    "s": "D",         # strikethrough/Del
    "link": "L",      # Link
}

SINGLE_TRANSLATE_CODES = {
    "image": "G",     # imaGe
}

PROTECT_CODES = {
    "code_inline": "C",
    "math_inline": "M",
    "html_inline": "X",
    "footnote_ref": "F",
    "tasklist_item": "T",
    "softbreak": "S",
    "hardbreak": "H",
}

# Разделитель сегментов (предложений) внутри чанка
SEGMENT_SEPARATOR = " __S__ "
```

**Контекст пробелов:**
Каждый `Placeholder` хранит флаги `has_leading_space` и `has_trailing_space`, которые определяют, нужны ли пробелы до/после плейсхолдера при восстановлении. Это критично для корректной работы с NLLB, которая нормализует пробелы.

### Чанкер (Chunker)

**Проблема:** NLLB имеет лимит на количество токенов в запросе. Длинные документы нужно разбивать на части.

**Решение:**
1. Группировка `TranslationUnit` в чанки с учетом лимита токенов
2. Объединение сегментов через разделитель `SEGMENT_SEPARATOR` (`" __S__ "`) из `placeholder_codes.py`
3. После перевода - разбиение по разделителю и merge обратно в `TranslationUnit`

**Особенности:**
- Используется `settings.max_input_tokens` из конфига
- Fallback-алгоритм для случаев, когда NLLB изменила структуру чанка
- Поддержка длинных предложений через `_safe_split_long_sentence()`

### Реконструктор

Собирает финальный Markdown из списка `TranslationUnit`:

1. **StateMachine** - отслеживает стек открытых блоков (цитаты, списки) для правильных префиксов
2. **BlockWriter** - записывает текст с учетом префиксов (например, `> ` для цитат)
3. **PlaceholderRestorer** - восстанавливает плейсхолдеры обратно в Markdown-разметку
4. **CodeBlockHandler** - специальная обработка блоков кода (не добавлять префиксы внутри кода)
5. **TableHandler** - сборка таблиц из ячеек

## Требования к модулю

### Функциональные требования

1. **Сохранение структуры документа:**
   - Заголовки остаются заголовками
   - Списки остаются списками с правильной вложенностью
   - Таблицы сохраняют структуру
   - Блоки кода не переводятся

2. **Корректная обработка inline-элементов:**
   - `**bold**` → `**жирный**` (сохранение маркеров)
   - `[текст](url)` → `[перевод](url)` (перевод текста ссылки)
   - `` `код` `` → `` `код` `` (код не переводится)
   - `![alt](src)` → `![перевод_alt](src)` (перевод alt-текста)

3. **Поддержка расширенного синтаксиса:**
   - Front matter (YAML)
   - Definition lists
   - Task lists с чекбоксами
   - Footnotes
   - Math formulas (`$...$`)

4. **Обработка edge cases:**
   - Вложенные списки с правильными отступами
   - Блоки кода внутри цитат
   - Множественные fence-блоки
   - Пустые документы и пустые строки

### Нефункциональные требования

1. **Производительность:**
   - Обработка документов до 10,000 токенов
   - Разбиение на чанки не должно терять контекст
   - Fallback-алгоритм должен работать за O(n)

2. **Надежность:**
   - Graceful degradation при ошибках NLLB
   - Сохранение исходного текста при невозможности перевода
   - Детальное логирование для отладки

3. **Расширяемость:**
   - Легкое добавление новых типов AST-узлов
   - Модульная архитектура handlers
   - Централизованный словарь кодов плейсхолдеров

## Тестирование

### Структура тестов

```
tests/markdown2/
├── conftest.py                              # Фикстуры (mock_translator, integration_translation_dict)
├── test_markdown_ast_walker.py              # Тесты обхода AST
├── test_markdown_chunker.py                 # Тесты чанкера
├── test_markdown_placeholder_manager.py     # Тесты плейсхолдеров
├── test_markdown_reconstructor.py           # Тесты реконструктора
├── test_markdown_elements.py                # Интеграционные тесты элементов
├── test_markdown_integration.py             # Сквозные интеграционные тесты
├── test_translation_unit.py                 # Тесты моделей данных
└── test_known_bugs.py                       # Regression-тесты известных багов
```

### Типы тестов

1. **Unit-тесты** - проверка отдельных компонентов:
   - `test_markdown_ast_walker.py` - корректность обхода AST
   - `test_markdown_chunker.py` - разбиение и merge чанков
   - `test_markdown_placeholder_manager.py` - создание и восстановление плейсхолдеров

2. **Интеграционные тесты** - проверка взаимодействия компонентов:
   - `test_markdown_elements.py` - перевод отдельных элементов (таблицы, списки, код)
   - `test_markdown_integration.py` - сквозной перевод полного документа

3. **Regression-тесты** - проверка исправления известных багов:
   - `test_known_bugs.py` - специфические edge cases

### Запуск тестов

```bash
# Все тесты markdown2
uv run pytest tests/markdown2/ -v

# Конкретный тест-файл
uv run pytest tests/markdown2/test_markdown_integration.py -v

# Конкретный тест
uv run pytest tests/markdown2/test_markdown_integration.py::test_full_pipeline -v
```

### Mock-движок для тестов

В `conftest.py` используется `MockTranslationEngine`, который имитирует NLLB через словарь переводов:

```python
@pytest.fixture
def integration_translation_dict():
    return {
        # Сегменты с плейсхолдерами, отделёнными пробелами
        "This is __B_O_1__ bold __B_C_1__  text.": "Это __B_O_1__ жирный __B_C_1__  текст.",
        "Go to __L_O_2__ Google __L_C_2__ .": "Перейдите на __L_O_2__ Google __L_C_2__ .",
        "__T_1__  Done task": "__T_1__  Выполненная задача",
        # ... другие переводы
    }

@pytest.fixture
def mock_translator(mock_engine, integration_translation_dict):
    def _create_translator(text: str, translation_dict=None):
        engine = mock_engine(translation_dict or integration_translation_dict)
        return MarkdownTranslator(text=text, src_lang="eng_Latn", tgt_lang="rus_Cyrl",
                                  engine=engine, max_tokens=100)
    return _create_translator
```

**Важно:** В тестах используются dunder-плейсхолдеры (`__B_O_1__`), а не старые фигурные скобки (`{s_1}`).

## Архитектурные правила

### 1. Разделение ответственности

Каждый подмодуль отвечает за свой этап пайплайна:
- `ast_walker/` - только обход AST и создание `TranslationUnit`
- `chunker.py` - только разбиение и merge чанков
- `reconstructor/` - только сборка финального Markdown
- `models/` - только модели данных (без бизнес-логики)

**Нарушение:** Если компонент начинает делать работу другого компонента, это сигнал к рефакторингу.

### 2. Immutability моделей

`TranslationUnit` и `Placeholder` должны быть максимально неизменяемыми. Изменения допустимы только в рамках одного этапа пайплайна:
- `ast_walker` заполняет `extracted_text` и `placeholders`
- `chunker` заполняет `translated_text`
- `reconstructor` читает все поля, но не изменяет

### 3. Централизация конфигурации

- Словарь кодов плейсхолдеров - только в `models/placeholder_codes.py`
- Маппинг типов узлов - только в `models/node_type.py`
- Конфигурация лимитов - только в `config.py`

**Запрещено:** Хардкодить коды плейсхолдеров или типы узлов в других файлах.

### 4. Явные зависимости

Компоненты не должны импортировать друг друга напрямую. Зависимости передаются через конструктор:

```python
# ✅ Правильно
class MarkdownTranslator:
    def __init__(self, text, src_lang, tgt_lang, engine, max_tokens):
        self.chunker = MarkdownChunker(tokenizer=engine.tokenizer, max_tokens=max_tokens)
        self.reconstructor = MarkdownReconstructor()

# ❌ Неправильно
class MarkdownTranslator:
    def __init__(self, text, src_lang, tgt_lang, engine):
        self.chunker = MarkdownChunker()  # chunker сам достает engine из глобального контекста
```

### 5. Обработка ошибок

- Каждый этап должен ловить свои ошибки и логировать их
- При ошибке перевода чанка - использовать оригинальный текст (graceful degradation)
- При ошибке восстановления плейсхолдера - оставить плейсхолдер как есть

```python
try:
    translated = engine.translate(plain_text, src_lang, tgt_lang)
except Exception as e:
    logger.error(f"Translation failed: {e}")
    translated = plain_text  # fallback к оригиналу
```

### 6. Логирование

- Использовать `logger` из стандартной библиотеки `logging`
- Уровень `DEBUG` - для детальной отладки (обход AST, создание плейсхолдеров)
- Уровень `INFO` - для ключевых этапов (начало перевода, завершение)
- Уровень `ERROR` - для ошибок с полным контекстом

### 7. Тестирование изменений

**Обязательное правило:** Любое изменение в модуле `markdown2` должно сопровождаться:
1. Запуском всех тестов: `uv run pytest tests/markdown2/ -v`
2. Проверкой линтера: `uv run ruff check src/mt_server/markdown2/`
3. Если добавлен новый функционал - добавлением соответствующих тестов

## Известные ограничения

1. **NLLB не понимает Markdown:** Модель пытается перевести разметку как текст, поэтому необходима система плейсхолдеров.

2. **Нормализация пробелов:** NLLB может удалять или добавлять пробелы вокруг плейсхолдеров. Система добавляет пробелы вокруг каждого плейсхолдера на этапе AST-walk (`InlineCollector._append_tag()`), а `PlaceholderRestorer.normalize_text()` при реконструкции убирает лишние пробелы между закрывающими плейсхолдерами и пунктуацией.

3. **Лимит токенов:** NLLB имеет жесткий лимит на входную длину, что требует разбиения документов на чанки.

4. **Нет поддержки HTML-блоков:** Большие HTML-блоки не переводятся корректно (только inline HTML).

5. **Сложные таблицы:** Таблицы с объединенными ячейками (colspan/rowspan) могут терять структуру.

## Планы развития

См. `plans/refactoring_markdown2_plan.md` для детального плана рефакторинга.

**Текущий статус:**
- ✅ Фаза 0: Подготовительная (выполнена)
- ✅ Фаза 0b: Очистка оркестратора (выполнена)
- ✅ Фаза 0c: Структурная реорганизация (выполнена)
- ✅ Фаза 0d: Рефакторинг плейсхолдеров (выполнена)
- ✅ Пробелы вокруг плейсхолдеров (выполнено) — все плейсхолдеры в `extracted_text` отделены пробелами от текста; `SEGMENT_SEPARATOR` централизован в `placeholder_codes.py`
- ⏳ Фаза 1: Устранение циклических зависимостей (в ожидании)
- ⏳ Фаза 2: Консолидация дублирования (в ожидании)

## Связанные файлы

- `src/mt_server/translation_service.py` - сервис перевода, использующий markdown2
- `src/mt_server/handlers.py` - HTTP-обработчики
- `src/mt_server/engine.py` - интерфейс к NLLB-модели
- `src/mt_server/config.py` - конфигурация (включая `max_input_tokens`)
- `tests/markdown2/` - тесты модуля
- `plans/refactoring_markdown2_plan.md` - план рефакторинга
