# Техническая спецификация системы перевода Markdown v2.0
## (Улучшенная версия на основе анализа реализации)

---

## 1. Обзор системы

Система переводит Markdown-документы с сохранением всей структуры форматирования, включая вложенность, списки, таблицы, код, математические формулы и другие элементы.

### 1.1 Архитектура (уточненная)

```
┌─────────────────────────────────────────────────────────────┐
│                    Markdown Translation Pipeline             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Parser    │───▶│   AST       │───▶│   Walker    │      │
│  │             │    │   Root      │    │             │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│         │                   │                   │            │
│         ▼                   ▼                   ▼            │
│  markdown-it-py      SyntaxTreeNode      DFS + Stack         │
│  + mdit-py-plugins                       Context Tracking    │
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Placeholder │◀───│ Translation │◀───│  Chunking   │      │
│  │   Manager   │    │   Units     │    │   Engine    │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│         │                   │                   │            │
│         ▼                   ▼                   ▼            │
│  Tag Mask Generator   Flat List       \x1E Separator        │
│  LIFO Stack for Pairs  + Metadata    Token-aware Split      │
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   State     │◀───│   Merger    │◀───│ Translation │      │
│  │   Machine   │    │   Fallback  │    │   Engine    │      │
│  │  Reconstr.  │    │   Align     │    │   (NLLB)    │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│         │                   │                   │            │
│         ▼                   ▼                   ▼            │
│  Block Stack +       \x1E Split +      Batch API            │
│  Prefix Calculator   Mask Anchor       + Error Handling     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Основные компоненты (актуализированные)

1. **Parser** (`parser.py`) - парсит Markdown в AST с использованием `markdown-it-py` + `mdit-py-plugins`
2. **ASTWalker** (`ast_walker.py`) - обходит дерево DFS, классифицирует узлы, управляет стеком контекстов
3. **PlaceholderManager** (`placeholder.py`) - создает маски `{prefix_id}` для защиты элементов
4. **TranslationUnit** (`translation_unit.py`) - единица перевода с метаданными и плейсхолдерами
5. **MarkdownChunker** (`chunker.py`) - разбивает на чанки с разделителем `\x1E`, мержит ответы
6. **MarkdownReconstructor** (`reconstructor.py`) - state machine для обратной сборки Markdown
7. **MarkdownTranslator** (`markdown_translator.py`) - оркестратор полного конвейера

---

## 2. Парсинг Markdown в AST

### 2.1 Используемые библиотеки

```python
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.table import table_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.field_list import fieldlist_plugin
```

### 2.2 Конфигурация парсера

```python
def create_markdown_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark")

    # Встроенные плагины
    md.enable("table")

    # Внешние плагины
    md.use(footnote_plugin)
    md.use(tasklists_plugin)
    md.use(deflist_plugin)
    md.use(dollarmath_plugin)
    md.use(front_matter_plugin)
    md.use(attrs_plugin)
    md.use(anchors_plugin)
    md.use(fieldlist_plugin)

    return md
```

### 2.3 Типы узлов AST (из реализации)

| Категория | Типы узлов | Пример |
|-----------|------------|--------|
| **CONTEXT_BLOCK** | `paragraph_open/close`, `heading_open/close`, `th_open/close`, `td_open/close`, `dt_open/close`, `dd_open/close`, `footnote_open/close`, `field_name_open/close`, `field_body_open/close` | Текст для перевода |
| **INLINE_TRANSLATE** | `strong_open/close`, `em_open/close`, `s_open/close`, `link_open/close`, `image` | Форматирование + текст |
| **INLINE_PROTECT** | `code_inline`, `math_inline`, `html_inline`, `footnote_ref`, `tasklist_item`, `softbreak`, `hardbreak` | Защита плейсхолдером |
| **STRUCTURAL_IGNORE** | `fence`, `code_block`, `math_block`, `html_block`, `table_open/close`, `thead_open/close`, `tbody_open/close`, `tr_open/close`, `blockquote_open/close`, `bullet_list_open/close`, `ordered_list_open/close`, `list_item_open/close`, `footnote_block_open/close`, `dl_open/close`, `field_list_open/close`, `field_open/close`, `hr`, `inline`, `document` | Каркас документа |
| **SPECIAL_CASE** | `front_matter` | YAML метаданные |

---

## 3. Классификация узлов (уточненная)

### 3.1 Стратегии обработки (TranslationUnitType)

```python
class TranslationUnitType(StrEnum):
    CONTEXT_BLOCK = "context_block"      # Текстовый контейнер (переводится целиком)
    INLINE_TRANSLATE = "inline_translate" # Inline-элемент, текст внутри переводится
    INLINE_PROTECT = "inline_protect"     # Нетранслируемый инлайн (изолируется плейсхолдером)
    STRUCTURAL_IGNORE = "structural_ignore" # Структурный шум (сохраняет каркас)
    SPECIAL_CASE = "special_case"         # Требует кастомной логики (Front Matter)
```

### 3.2 Правила классификации (из node_type.py)

#### 3.2.1 CONTEXT_BLOCK - текстовые контейнеры

| Узел | Правило | Пример |
|------|---------|--------|
| `paragraph_open/close` | Весь текст внутри параграфа переводится | `This is text` |
| `heading_open/close` | Текст заголовка переводится, уровень сохраняется | `# Title` |
| `th_open/close` | Текст ячейки шапки таблицы | `| Header |` |
| `td_open/close` | Текст ячейки тела таблицы | `| Cell |` |
| `dt_open/close` | Термин в списке определений | `Term` |
| `dd_open/close` | Определение в списке определений | `Definition` |
| `footnote_open/close` | Содержимое сноски | `[^1]: text` |
| `field_name_open/close` | Имя поля в field_list | `:name:` |
| `field_body_open/close` | Тело поля в field_list | `value` |

#### 3.2.2 INLINE_TRANSLATE - транслируемые инлайны

| Узел | Правило | Пример |
|------|---------|--------|
| `strong_open/close` | Жирный текст переводится, маркер `**` сохраняется | `**bold**` |
| `em_open/close` | Курсивный текст переводится, маркер `*` сохраняется | `*italic*` |
| `s_open/close` | Зачеркнутый текст переводится, маркер `~~` сохраняется | `~~strikethrough~~` |
| `link_open/close` | Переводится только текст ссылки, URL сохраняется | `[text](url)` |
| `image` | Переводится alt текст, URL сохраняется | `![alt](url)` |

#### 3.2.3 INLINE_PROTECT - защищаемые атомарные инлайны

| Узел | Правило | Пример |
|------|---------|--------|
| `code_inline` | Inline код не переводится, защищается плейсхолдером | `` `code` `` |
| `math_inline` | Inline математика не переводится | `$x + y$` |
| `html_inline` | Inline HTML не переводится | `<span>` |
| `footnote_ref` | Маркер сноски не переводится | `[^1]` |
| `tasklist_item` | Чекбокс задачи не переводится | `- [x]` |
| `softbreak` | Мягкий перенос сохраняется как `\n` | `\n` |
| `hardbreak` | Жесткий перенос сохраняется как `<br>` | `<br>` |

#### 3.2.4 STRUCTURAL_IGNORE - структурные блоки

| Узел | Правило | Пример |
|------|---------|--------|
| `fence` | Fenced code block не переводится целиком | ```python\ncode\n``` |
| `code_block` | Indented code block не переводится | 4 пробела + код |
| `math_block` | Блочная математика не переводится | `$$x + y$$` |
| `html_block` | HTML блок не переводится | `<div>` |
| `table_open/close` | Структура таблицы сохраняется | `| a | b |` |
| `thead_open/close` | Структура шапки таблицы | - |
| `tbody_open/close` | Структура тела таблицы | - |
| `tr_open/close` | Структура строки таблицы | - |
| `blockquote_open/close` | Структура цитаты сохраняется | `> text` |
| `bullet_list_open/close` | Структура маркированного списка | `- item` |
| `ordered_list_open/close` | Структура нумерованного списка | `1. item` |
| `list_item_open/close` | Структура элемента списка | - |
| `footnote_block_open/close` | Блок сносок | - |
| `dl_open/close` | Список определений | - |
| `field_list_open/close` | Список полей | - |
| `field_open/close` | Поле в field_list | - |
| `hr` | Горизонтальная линия | `---` |
| `inline` | Контейнер инлайн-элементов (игнорируется) | - |
| `document` | Корневой элемент (игнорируется) | - |

#### 3.2.5 SPECIAL_CASE - специальные случаи

| Узел | Правило | Пример |
|------|---------|--------|
| `front_matter` | YAML метаданные обрабатываются отдельно | `---\ntitle: Text\n---` |

---

## 4. Управление плейсхолдерами

### 4.1 Формат плейсхолдеров (из реализации)

```
{prefix_id}           - открывающий тег
{/prefix_id}          - закрывающий тег
```

**Префиксы:**
- `s` - strong (`**`)
- `e` - em (`*`)
- `lnk` - link
- `img` - image
- `code` - code_inline
- `math` - math_inline
- `html` - html_inline
- `fn` - footnote_ref
- `chk` - tasklist_item
- `br` - softbreak/hardbreak
- `ph` - fallback для неизвестных типов

**Примеры:**
- `{code_1}` - inline код
- `{math_2}` - математика
- `{lnk_1}текст{/lnk_1}` - ссылка с текстом
- `{s_1}жирный{/s_1}` - жирный текст
- `{img_1}` - изображение

### 4.2 Генерация уникальных ID

```python
class PlaceholderManager:
    def __init__(self):
        self._counter: int = 0
        self.registry: Dict[str, Placeholder] = {}
        self._open_tags_stacks: Dict[str, List[int]] = {}  # LIFO стек для парных тегов

    def create_placeholder(self, node: SyntaxTreeNode) -> Placeholder:
        # Для закрывающих тегов - берем ID из стека
        # Для открывающих - инкрементируем счетчик и пушим в стек
        # Для одиночных тегов (code, image) - просто инкрементируем
```

### 4.3 Структура Placeholder

```python
@dataclass
class Placeholder:
    id: int                              # Уникальный ID
    tag_mask: str                        # Маска вида " {prefix_id} "
    strategy: Literal["INLINE_TRANSLATE", "INLINE_PROTECT"]
    node_type: str                       # Тип узла AST
    original_markup: Union[str, Dict]    # Оригинальная разметка или атрибуты
    is_closing: bool = False             # Флаг закрывающего тега
```

---

## 5. Алгоритм чанкования (уточненный)

### 5.1 Стратегия чанкования

```python
@dataclass(slots=True)
class ChunkSegment:
    """Атомарная единица текста внутри чанка."""
    unit_id: str      # ID TranslationUnit
    text: str         # Текст сегмента

@dataclass(slots=True)
class MarkdownChunk:
    """Пакет данных для передачи в NLLB."""
    chunk_id: int
    segments: List[ChunkSegment]
    token_count: int
    sentence_count: int

    def to_plain_text(self) -> str:
        # Использует непечатный ASCII символ \x1E (Record Separator)
        # NLLB гарантированно переносит его без изменений
        return "\x1e".join(seg.text for seg in self.segments)
```

### 5.2 Алгоритм создания чанков

```python
def create_chunks(self, units: List[TranslationUnit]) -> List[MarkdownChunk]:
    """
    Алгоритм упаковки юнитов в чанки:

    1. Фильтруем только юниты с need_translation=True
    2. Для каждого юнита разбиваем extracted_text на предложения (pysbd)
    3. Для каждого предложения:
       a. Считаем токены
       b. Если предложение > max_tokens, разбиваем на части (_safe_split_long_sentence)
       c. Если часть > max_tokens, обрабатываем как неделимый элемент
    4. Жадная упаковка: добавляем сегменты в текущий чанк пока <= max_tokens
    5. При превышении - создаем новый чанк
    6. Возвращаем список чанков
    """
```

### 5.3 Безопасное разбиение длинных предложений

```python
def _safe_split_long_sentence(self, sentence: str) -> List[str]:
    """
    Разбивает длинное предложение на части, сохраняя плейсхолдеры целыми.

    Использует regex: r"(\{[^}]+\})|(\s+)|(\S+)"
    - Группирует плейсхолдеры как единые токены
    - Разделяет по пробелам
    - Сохраняет отдельные слова
    """
```

### 5.4 Алгоритм слияния переводов (Merger)

```python
def merge_translations(
    self,
    chunks: List[MarkdownChunk],
    translated_texts: List[str],
    units: List[TranslationUnit]
):
    """
    Алгоритм обратной сборки:

    1. Создаем мапу unit_id -> TranslationUnit
    2. Инициализируем translated_text="" для всех нуждающихся в переводе
    3. Для каждого чанка и соответствующего ответа NLLB:
       a. Разбиваем ответ по \x1E на сегменты
       b. Если количество сегментов совпадает - мапим по порядку
       c. Если не совпадает - запускаем fallback по маскам-якорям
    4. Fallback алгоритм:
       a. Ищем маски {prefix_id} в переведенном тексте
       b. Находим匹配的 сегмент чанка по маске
       c. Привязываем перевод к соответствующему unit
       d. Несопоставленные сегменты распределяем хронологически
    """
```

---

## 6. Восстановление AST (State Machine)

### 6.1 Архитектура реконструктора

```python
class MarkdownReconstructor:
    """State Machine для линейной обратной сборки Markdown."""

    def __init__(self):
        self._buffer: List[str] = []
        self._block_stack: List[Dict[str, Any]] = []
        # Стек хранит: {"type": "...", "marker": "...", "is_first_paragraph": True}
```

### 6.2 Алгоритм реконструкции

```python
def reconstruct(self, units: List[TranslationUnit]) -> str:
    """
    Линейный обход плоского списка TranslationUnit:

    1. STRUCTURAL_IGNORE:
       - fence/code_block: пишем напрямую в буфер с префиксом вложенности
       - hr: пишем "---"
       - list/table/blockquote open: пушим в стек
       - list/table/blockquote close: снимаем со стека

    2. CONTEXT_BLOCK:
       - dt/dd open: пушим в стек для префиксации
       - heading: добавляем "#" * level
       - paragraph: восстанавливаем инлайн-плейсхолдеры
       - dt/dd close: снимаем со стека

    3. SPECIAL_CASE:
       - front_matter: оборачиваем в "---"

    4. Префиксация строк:
       - Вычисляем отступы по стеку (цитаты "> ", списки "    ")
       - Для list_item добавляем маркер "- " или "1. "
       - Для dd добавляем ": "
    """
```

### 6.3 Восстановление инлайн-плейсхолдеров

```python
def _restore_inline_placeholders(self, text: str, unit: TranslationUnit) -> str:
    """
    Двухэтапное восстановление:

    Этап 1: Парные теги (regex рекурсивно)
    - pattern: r"\{\s*([a-zA-Z]+)_(\d+)\s*\}(.*?)\{\s*/\1_\2\s*\}"
    - Заменяем {lnk_1}текст{/lnk_1} на [текст](url)
    - Заменяем {s_1}текст{/s_1} на **текст**

    Этап 2: Одиночные теги
    - pattern: r"\{\s*([a-zA-Z0-9_/]+)\s*\}"
    - Заменяем {code_1} на `code`
    - Заменяем {math_1} на $formula$
    - Заменяем {br_1} на \n или <br>
    - Заменяем {img_1} на ![alt](src)
    """
```

### 6.4 Префиксация вложенности

```python
def _get_current_prefix(self, for_block_start: bool = False) -> Tuple[str, str]:
    """
    Вычисляет префикс строки на основе стека:

    - blockquote: добавляет "> "
    - bullet_list/ordered_list: добавляет "    " для уровней > 1
    - list_item: добавляет "- " или "1. " для первой строки
    - dd: добавляет ": " для первой строки, "  " для последующих
    """
```

---

## 7. Обработка edge cases (из реализации и плана)

### 7.1 Вложенные ссылки и изображения

**Решение:** Парные плейсхолдеры с рекурсивной заменой
```
{lnk_1}{img_2}{/img_2} текст ссылки{/lnk_1}
```

### 7.2 Экранированные символы

**Решение:** markdown-it-py автоматически обрабатывает экранирование, контент передается как text узлы

### 7.3 Многоязычный контент

**Решение:** pysbd определяет язык и сегментирует предложения соответственно

### 7.4 Длинные слова и URL

**Решение:** _safe_split_long_sentence защищает плейсхолдеры, разбивает по пробелам

### 7.5 Математические формулы с текстом

**Решение:** INLINE_PROTECT стратегия - вся формула защищается одним плейсхолдером

### 7.6 Ссылки с title

**Решение:** Сохраняем в original_markup как dict {"href": "...", "title": "..."}

### 7.7 Вложенные списки

**Решение:** Стек block_stack отслеживает уровень, добавляет "    " отступ для каждого уровня

### 7.8 Таблицы с многострочными ячейками

**Текущее состояние:** Структура таблиц сохраняется через STRUCTURAL_IGNORE, но контент ячеек требует доработки

**Рекомендация:** Обрабатывать td/th как CONTEXT_BLOCK с восстановлением переносов строк

### 7.9 HTML внутри Markdown

**Решение:** html_inline и html_block как INLINE_PROTECT/STRUCTURAL_IGNORE

### 7.10 Reference-style ссылки

**Текущее состояние:** Не реализовано явно

**Рекомендация:** Добавить обработку link_reference_definition как STRUCTURAL_IGNORE

### 7.11 Task lists

**Текущее состояние:** tasklist_item как INLINE_PROTECT

**Рекомендация:** Восстанавливать чекбокс `- [x]` в reconstructor

### 7.12 Footnotes

**Текущее состояние:** footnote_ref как INLINE_PROTECT, footnote_block как STRUCTURAL_IGNORE

**Рекомендация:** Обеспечить корректную нумерацию при восстановлении

---

## 8. Обработка ошибок и валидация

### 8.1 Типы ошибок

| Тип ошибки | Описание | Обработка |
|------------|----------|-----------|
| `ParseError` | Ошибка парсинга Markdown | Возвращаем оригинальный текст |
| `TranslationError` | Ошибка перевода NLLB | Пропускаем чанк, логируем |
| `PlaceholderMismatch` | Несоответствие плейсхолдеров | Fallback alignment по маскам |
| `TokenLimitExceeded` | Превышен лимит токенов | _safe_split_long_sentence |
| `SegmentDrop` | NLLB пропустил сегмент | Хронологическое распределение + флаг has_errors |

### 8.2 Валидация AST (рекомендация)

```python
def validate_ast(ast: SyntaxTreeNode) -> List[str]:
    """
    Проверки:
    - Баланс открывающих/закрывающих тегов
    - Корректная вложенность списков
    - Структура таблиц (thead before tbody)
    """
```

### 8.3 Обработка ошибок в Merger

```python
def _fallback_align_segments(...):
    """
    Аварийный алгоритм:
    1. Ищем маски-якоря в переведенном тексте
    2. Матчим с сегментами чанка
    3. Несопоставленные распределяем хронологически
    4. Потерянные сегменты помечаем has_errors=True
    """
```

---

## 9. Производительность и оптимизация

### 9.1 Кэширование (рекомендация)

```python
@lru_cache(maxsize=32)
def get_segmenter(nllb_lang_code: str):
    """Кэширует pysbd.Segmenter по языку."""
```

### 9.2 Токенизация

```python
def count_tokens(tokenizer, text: str) -> int:
    """Вызывает tokenizer один раз, возвращает len(input_ids)."""
```

### 9.3 Пакетная обработка

**Текущее состояние:** Последовательный вызов engine.translate для каждого чанка

**Рекомендация:** Добавить batch_translate API для параллельной обработки

---

## 10. Тестирование

### 10.1 Покрытие тестами (из реализации)

| Компонент | Тесты | Покрытие |
|-----------|-------|----------|
| ASTWalker | 6 тестов | plain paragraph, inline formatting, nested blocks, front matter, multiple contexts, structural inside context |
| PlaceholderManager | 7 тестов | code, math, paired tags stack, link attributes, image, unbalanced closing, unknown type |
| MarkdownChunker | 9 тестов | greedy packing, max tokens split, mask protection, indivisible token, merge ideal, merge fallback by masks, merge chronological drop, empty segments, empty units |
| MarkdownReconstructor | 9 тестов | plain paragraph, heading, inline strong, links/images, nested blockquote, front matter, nested lists, definition lists, fence inside blockquote |
| Integration | 4 теста | full pipeline, empty inputs |

### 10.2 Рекомендуемые дополнительные тесты

| Сценарий | Описание | Приоритет |
|----------|----------|-----------|
| `tables` | Таблицы с кодом и ссылками | Высокий |
| `task-lists` | Списки задач с чекбоксами | Высокий |
| `footnotes` | Сноски с маркерами | Средний |
| `reference-links` | Reference-style ссылки | Средний |
| `html-blocks` | HTML блоки внутри Markdown | Средний |
| `escaped-markdown` | Экранированный Markdown | Низкий |
| `malformed-markdown` | Невалидный Markdown | Низкий |
| `huge-documents` | Большие документы (>10K токенов) | Высокий |
| `unicode-punctuation` | Unicode пунктуация | Низкий |
| `rtl-languages` | RTL языки (арабский, иврит) | Низкий |

---

## 11. Известные проблемы и технические долги

### 11.1 Несоответствие тестов и реализации

**Проблема:** В тестах используется разделитель ` ||| `, но в реализации `\x1e`

**Решение:** Обновить тесты на использование `\x1e`

### 11.2 Обработка таблиц

**Проблема:** Таблицы обрабатываются как STRUCTURAL_IGNORE, но контент ячеек (th/td) должен переводиться

**Решение:** Убедиться что th_open/close и td_open/close правильно классифицированы как CONTEXT_BLOCK

### 11.3 Tasklist восстановление

**Проблема:** tasklist_item защищается плейсхолдером, но не восстанавливается в reconstructor

**Решение:** Добавить обработку в _restore_inline_placeholders

### 11.4 Отсутствие валидации

**Проблема:** Нет явной валидации AST перед рендерингом

**Решение:** Добавить validate_ast() вызов перед reconstruct()

### 11.5 Обработка ошибок перевода

**Проблема:** Минимальная обработка ошибок NLLB

**Решение:** Добавить retry logic, circuit breaker, detailed logging

---

## 12. Roadmap улучшений

### Фаза 1: Стабилизация (недели 1-2)
- [x] Исправить несоответствие тестов (`|||` → `\x1e`)
- [x] Добавить тесты для таблиц
- [x] Добавить тесты для task lists
- [ ] Реализовать валидацию AST
- [x] **Добавить логирование в uvicorn.error**:

### Фаза 2: Функциональность (недели 3-4)
- [ ] Полная поддержка таблиц (многострочные ячейки)
- [ ] Восстановление tasklist checkbox
- [ ] Поддержка reference-style ссылок
- [ ] Поддержка footnotes с нумерацией

### Фаза 3: Производительность (недели 5-6)
- [ ] Batch translation API
- [ ] Parallel chunk processing
- [ ] Advanced caching

### Фаза 4: Надежность (недели 7-8)
- [ ] Retry logic для NLLB
- [ ] Circuit breaker pattern
- [ ] Comprehensive error logging
- [ ] Metrics collection

---

## 13. Заключение

Текущая реализация представляет собой зрелую систему с четкой архитектурой:

**Сильные стороны:**
1. ✅ Четкое разделение ответственности между компонентами
2. ✅ Стековая архитектура для вложенных контекстов
3. ✅ Надежная система плейсхолдеров с LIFO для парных тегов
4. ✅ Умное чанкование с защитой масок
5. ✅ Fallback алгоритм для аномалий NLLB
6. ✅ State machine для реконструкции
7. ✅ Хорошее тестовое покрытие основных сценариев

**Области улучшения:**
1. ⚠️ Несогласованность тестов с реализацией
2. ⚠️ Неполная поддержка таблиц
3. ⚠️ Отсутствует валидация AST
4. ⚠️ Минимальная обработка ошибок
5. ⚠️ Нет batch/parallel обработки

**Рекомендация:** Сфокусироваться на Фазе 1 (стабилизация) перед добавлением новой функциональности.