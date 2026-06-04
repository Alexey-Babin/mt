Теперь у меня есть полное представление о структуре модуля markdown2.
Проведу анализ и составлю план рефакторинга.

## Анализ модуля markdown2

### Текущая структура

``` qwen-markdown-code
12345678910111213141516171819202122232425markdown2/├── markdown_translator.py      (135 строк) - точка входа├── parser.py                   (32 строки)  - создание парсера├── ast_walker.py               (116 строк)  - обход AST├── chunker.py                  (249 строк)  - нарезка на чанки├── translation_unit.py         (41 строка)  - модель данных├── translation_unit_type.py    (16 строк)   - enum типов├── node_type.py                (116 строк)  - маппинг типов узлов├── unit_factory.py             (91 строка)  - фабрика юнитов├── placeholder.py              (171 строка) - плейсхолдеры├── reconstructor.py            (602 строки) - СБОРКА (дублирует подмодуль!)└── handlers/                   (544 строки)│   ├── context_block_handler.py    (190 строк)│   ├── structural_block_handler.py (145 строк)│   ├── special_case_handler.py     (69 строк)│   ├── inline_collector.py         (137 строк)│   └── __init__.py                 (13 строк)└── reconstructor/              (1006 строк)    ├── main.py                     (298 строк)    ├── state_machine.py            (170 строк)    ├── block_writer.py             (99 строк)    ├── placeholder_restorer.py     (241 строка)    ├── table_handler.py            (93 строки)    ├── code_block_handler.py       (48 строк)    └── __init__.py                 (27 строк)
```

### Выявленные проблемы

1.  **Критическое дублирование: `reconstructor.py` (602 строки)**
    - Файл существует параллельно с подмодулем `reconstructor/`
    - Содержит ту же логику, что уже декомпозирована в подмодуле
    - Это главный источник путаницы
2.  **Запутанный поток управления в AST Walker**
    - `_traverse()` делегирует handlers, но также имеет метод
      `_collect_inline()`
    - `InlineCollector` обращается обратно к
      `walker._context_block_handler` (циклическая зависимость)
    - Логика обработки закрывающих тегов размазана между
      `ContextBlockHandler` и `InlineCollector`
3.  **Избыточная сложность handlers**
    - `ContextBlockHandler` использует стек кортежей
      `(TranslationUnit, PlaceholderManager)`
    - При этом логика закрытия контекста дублируется в `_handle_close()`
      и `InlineCollector.collect()`
    - Метод `handle_node()` имеет множественные пути возврата
4.  **Неоптимальная структура node_type.py**
    - Множественные словари для группировки типов
    - Динамическая сборка `_NODE_TYPE_MAP` усложняет понимание
    - Можно упростить до прямого маппинга
5.  **PlaceholderManager слишком связан с AST**
    - Принимает `SyntaxTreeNode` напрямую
    - Извлечение `original_markup` смешано с логикой ID
    - Метод `_create_closing_placeholder()` — костыль для парных тегов
6.  **Chunker содержит аварийный fallback**
    - `_fallback_align_segments()` — 50 строк dead code для аномалий
      NLLB
    - Усложняет тестирование основного потока
7.  **MarkdownTranslator смешивает оркестрацию и конфигурацию**
    - Читает `settings.max_input_tokens` на уровне модуля
    - Создает компоненты в `__init__`, хотя некоторые нужны только в
      `process()`

------------------------------------------------------------------------

## План рефакторинга

### Фаза 1: Устранение дублирования (приоритет высокий)

**1.1. Удалить `reconstructor.py`**

- Файл полностью дублирует функциональность подмодуля `reconstructor/`

- Обновить импорты в `markdown_translator.py`:

  ``` qwen-markdown-code
  python12345# Было:from .reconstructor import MarkdownReconstructor# Стало (уже правильно в подмодуле):from .reconstructor.main import MarkdownReconstructor
  ```

### Фаза 2: Упрощение AST Walker и Handlers

**2.1. Рефакторинг `ast_walker.py`**

- Убрать метод `_collect_inline()`, сделать его приватным методом
  `InlineCollector`

- Упростить `_traverse()` до единого паттерна dispatch:

  ``` qwen-markdown-code
  python12345678910def _traverse(self, node, parent_id, index):    if node.type in ("root", "document"):        self._traverse_children(node, parent_id)        return        handler = self._get_handler_for_node(node)    if handler:        handler.handle(node, parent_id, index, self._traverse_children)    else:        self._traverse_children(node, parent_id)
  ```

**2.2. Объединить логику закрытия контекста**

- В `ContextBlockHandler` убрать обработку `_close` через отдельный
  метод
- Сделать единый метод `handle_open()` который возвращает callback для
  закрытия
- `InlineCollector` не должен модифицировать стек контекстов

**2.3. Убрать циклическую зависимость**

- `InlineCollector` не должен обращаться к
  `walker._context_block_handler`
- Передавать текущий контекст явно через параметры метода `collect()`

### Фаза 3: Упрощение node_type.py

**3.1. Заменить динамическую сборку на прямой словарь**

``` qwen-markdown-code
python123456789# Вместо множественных set и циклов заполнения:NODE_TYPE_MAP = {    # Context blocks    "paragraph": TranslationUnitType.CONTEXT_BLOCK,    "paragraph_open": TranslationUnitType.CONTEXT_BLOCK,    "paragraph_close": TranslationUnitType.CONTEXT_BLOCK,    "heading": TranslationUnitType.CONTEXT_BLOCK,    # ... и так далее явно}
```

- Удалить `_BLOCK_TYPES`, `_INLINE_TRANSLATE_PAIRED` и другие
  промежуточные множества
- Оставить только `get_unit_type()` с прямым lookup

### Фаза 4: Изоляция PlaceholderManager

**4.1. Разделить ответственность**

- Создать `PlaceholderIdManager` — только генерация ID и маппинг
- Создать `MarkupExtractor` — извлечение original_markup из узла
- `Placeholder` сделать frozen dataclass без методов

**4.2. Убрать `_create_closing_placeholder()`**

- Вместо этого создавать оба placeholder одновременно при обработке
  парного тега
- Использовать один ID для обоих

### Фаза 5: Очистка Chunker

**5.1. Удалить `_fallback_align_segments()`**

- Если аномалии NLLB редки — вынести в отдельный модуль
  `chunker_fallback.py`
- Подключать только через опцию конфига

**5.2. Выделить `SentenceSplitter`**

- Метод `split_sentences` сейчас импортируется из `utils`
- Создать класс-обертку для языково-зависимого сплиттера

### Фаза 6: Упрощение MarkdownTranslator

**6.1. Lazy initialization компонентов**

``` qwen-markdown-code
python1234567891011def __init__(self, text, src_lang, tgt_lang, engine):    self.text = text    self.src_lang = src_lang    self.tgt_lang = tgt_lang    self.engine = engine    # Не создаем компоненты здесьdef _get_chunker(self):    if not hasattr(self, '_chunker'):        self._chunker = MarkdownChunker(...)    return self._chunker
```

**6.2. Выделить конфигурацию в отдельный dataclass**

``` qwen-markdown-code
python12345678@dataclassclass MarkdownTranslatorConfig:    max_tokens: int    debug_mode: bool    class MarkdownTranslator:    def __init__(self, text, src_lang, tgt_lang, engine, config=None):        self.config = config or MarkdownTranslatorConfig(...)
```

### Фаза 7: Новая структура модуля

``` qwen-markdown-code
123456789101112131415161718192021markdown2/├── __init__.py                 - публичный API (MarkdownTranslator)├── translator.py               - было markdown_translator.py├── parser.py                   - без изменений├── ast_walker.py               - упрощенный dispatcher├── chunker.py                  - без fallback├── reconstructor/              - без изменений (уже хорошо)├── types.py                    - было translation_unit_type.py + node_type.py├── units.py                    - было translation_unit.py + unit_factory.py├── placeholders/               - новый подмодуль│   ├── __init__.py│   ├── models.py               - Placeholder dataclass│   ├── id_manager.py           - генерация ID│   └── markup_extractor.py     - извлечение разметки└── handlers/                   - упрощенные    ├── __init__.py    ├── base.py                 - базовый класс Handler    ├── context.py              - было context_block_handler.py    ├── structural.py           - было structural_block_handler.py    ├── special.py              - было special_case_handler.py    └── inline.py               - было inline_collector.py
```

### Итоговые метрики после рефакторинга

[TABLE]

------------------------------------------------------------------------

## Рекомендации по порядку выполнения

1.  **Сначала тесты** — убедиться, что все тесты в `tests/markdown2/`
    проходят
2.  **Фаза 1** — удалить `reconstructor.py` (самое простое и безопасное)
3.  **Фаза 3** — упростить `node_type.py` (минимальный риск)
4.  **Фаза 7** — переименовать файлы согласно новой структуре
5.  **Фаза 2** — рефакторинг handlers (требует тщательного тестирования)
6.  **Фазы 4-6** — опциональные улучшения
