# Техническая спецификация системы перевода Markdown с сохранением форматирования

## 1. Обзор системы

Система переводит Markdown-документы с сохранением всей структуры форматирования, включая вложенность, списки, таблицы, код, математические формулы и другие элементы.

### 1.1 Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Markdown Translation System               │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   Parser    │───▶│   AST       │───▶│ Translation │       │
│  │             │    │   Builder   │    │   Engine    │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         │                   │                   │             │
│         ▼                   ▼                   ▼             │
│  markdown-it-py      SyntaxTreeNode      NLLB Engine         │
│  + mdit-py-plugins                                            │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │ Placeholder │◀───│   Chunking  │◀───│   AST       │       │
│  │   Manager   │    │   Engine    │    │   Walker    │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         │                   │                   │             │
│         ▼                   ▼                   ▼             │
│  Tag Generator      Chunk Splitter      Node Classifier       │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   AST       │◀───│   Text      │◀───│   Text      │       │
│  │Reconstructor│    │   Merger    │    │   Extractor │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         │                   │                   │             │
│         ▼                   ▼                   ▼             │
│  markdown-it-py      Chunk Merger      Text Collector         │
│                                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Основные компоненты

1. **Parser** - парсит Markdown в AST с использованием `markdown-it-py` + `mdit-py-plugins`
2. **AST Walker** - обходит дерево и классифицирует узлы
3. **Text Extractor** - извлекает переводимый текст с плейсхолдерами
4. **Chunking Engine** - разбивает текст на чанки для перевода
5. **Translation Engine** - переводит текст (NLLB)
6. **Text Merger** - объединяет переведенные чанки
7. **Placeholder Manager** - управляет плейсхолдерами
8. **AST Reconstructor** - восстанавливает AST с переведенным текстом

---

## 2. Парсинг Markdown в AST

### 2.1 Используемые библиотеки

```python
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.table import table_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklist import tasklist_plugin
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
    """Создает парсер Markdown с поддержкой расширенного синтаксиса."""
    md = MarkdownIt("commonmark")
    
    # Встроенные плагины
    md.enable("table")
    
    # Внешние плагины
    md.use(table_plugin)
    md.use(footnote_plugin)
    md.use(tasklist_plugin)
    md.use(deflist_plugin)
    md.use(dollarmath_plugin, enable_dollars=True)
    md.use(front_matter_plugin)
    md.use(attrs_plugin)
    md.use(anchors_plugin)
    md.use(fieldlist_plugin)
    
    return md
```

### 2.3 Типы узлов AST

| Тип узла | Описание | Пример |
|----------|----------|--------|
| `document` | Корневой узел документа | - |
| `heading_open` / `heading_close` | Заголовок | `# Title` |
| `paragraph_open` / `paragraph_close` | Параграф | `Text` |
| `text` | Текстовый узел | `Hello` |
| `code_inline` | Inline код | `` `code` `` |
| `fence` | Fenced code block | ```python\ncode\n``` |
| `code_block` | Indented code block | 4 пробела + код |
| `link_open` / `link_close` | Ссылка | `[text](url)` |
| `image` | Изображение | `![alt](url)` |
| `html_inline` | Inline HTML | `<span>` |
| `html_block` | HTML блок | `<div>` |
| `bullet_list_open` / `bullet_list_close` | Маркированный список | `- item` |
| `ordered_list_open` / `ordered_list_close` | Нумерованный список | `1. item` |
| `list_item_open` / `list_item_close` | Элемент списка | - |
| `blockquote_open` / `blockquote_close` | Цитата | `> text` |
| `em_open` / `em_close` | Курсив | `*text*` |
| `strong_open` / `strong_close` | Жирный | `**text**` |
| `s_open` / `s_close` | Зачеркнутый | `~~text~~` |
| `table_open` / `table_close` | Таблица | `| a | b |` |
| `thead_open` / `thead_close` | Шапка таблицы | - |
| `tbody_open` / `tbody_close` | Тело таблицы | - |
| `tr_open` / `tr_close` | Строка таблицы | - |
| `th_open` / `th_close` | Ячейка шапки | - |
| `td_open` / `td_close` | Ячейка тела | - |
| `hr` | Горизонтальная линия | `---` |
| `softbreak` | Мягкий перенос | `\n` |
| `hardbreak` | Жесткий перенос | `<br>` |
| `front_matter` | YAML frontmatter | `---\ntitle: x\n---` |
| `math_inline` | Inline математика | `$x + y$` |
| `math_block` | Блочная математика | `$$x + y$$` |
| `footnote_ref` | Ссылка на сноску | `[^1]` |
| `footnote_block_open` / `footnote_block_close` | Блок сносок | - |
| `footnote_open` / `footnote_close` | Сноска | `[^1]: text` |
| `tasklist_item` | Элемент списка задач | `- [x] done` |
| `dl_open` / `dl_close` | Список определений | - |
| `dt_open` / `dt_close` | Термин | - |
| `dd_open` / `dd_close` | Определение | - |

---

## 3. Классификация узлов

### 3.1 Типы TranslationUnit

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class TranslationUnitType(Enum):
    """Тип единицы перевода."""
    
    # Полностью переводимые узлы
    FULL_TEXT = "full_text"           # Параграфы, заголовки, ячейки таблиц
    PARTIAL_TEXT = "partial_text"     # Узлы с частично переводимым текстом
    
    # Непереводимые узлы
    NON_TRANSLATABLE = "non_translatable"  # Код, математика, HTML
    STRUCTURAL = "structural"              # Структурные узлы (списки, таблицы)
    METADATA = "metadata"                  # Метаданные (frontmatter)
    
    # Специальные узлы
    LINK = "link"                     # Ссылки (переводим только текст)
    IMAGE = "image"                   # Изображения (переводим alt)
    FOOTNOTE = "footnote"             # Сноски (переводим содержимое)

@dataclass
class TranslationUnit:
    """Единица перевода с метаданными."""
    
    # Идентификация
    node_id: str                      # Уникальный ID узла
    node_type: str                    # Тип узла AST
    unit_type: TranslationUnitType    # Тип единицы перевода
    
    # Текст для перевода
    original_text: str                # Оригинальный текст
    extracted_text: str               # Извлеченный текст с плейсхолдерами
    translated_text: Optional[str] = None  # Переведенный текст
    
    # Плейсхолдеры
    placeholders: List[Placeholder] = None
    
    # Позиция в AST
    parent_id: Optional[str] = None
    index_in_parent: Optional[int] = None
    level: int = 0
    
    # Метаданные
    attrs: Optional[dict] = None      # Атрибуты узла
    tag: Optional[str] = None         # HTML тег
    info: Optional[str] = None        # Дополнительная информация (язык кода)
    
    # Статус
    is_translated: bool = False
    has_errors: bool = False
    error_message: Optional[str] = None
```

### 3.2 Правила классификации

#### 3.2.1 Полностью переводимые узлы (FULL_TEXT)

| Узел | Правило | Пример |
|------|---------|--------|
| `paragraph` | Весь текст внутри параграфа переводится | `This is text` |
| `heading` | Текст заголовка переводится, уровень сохраняется | `# Title` |
| `text` | Простой текстовый узел | `Hello` |
| `em` | Курсивный текст переводится | `*italic*` |
| `strong` | Жирный текст переводится | `**bold**` |
| `s` | Зачеркнутый текст переводится | `~~strikethrough~~` |
| `th` | Текст ячейки шапки таблицы | `| Header |` |
| `td` | Текст ячейки тела таблицы | `| Cell |` |
| `dt` | Термин в списке определений | `Term` |
| `dd` | Определение в списке определений | `Definition` |

#### 3.2.2 Частично переводимые узлы (PARTIAL_TEXT)

| Узел | Правило | Пример |
|------|---------|--------|
| `link` | Переводится только текст ссылки, URL сохраняется | `[text](url)` |
| `image` | Переводится alt текст, URL сохраняется | `![alt](url)` |
| `footnote` | Переводится содержимое сноски | `[^1]: text` |
| `front_matter` | Переводятся значения YAML, ключи сохраняются | `title: Text` |

#### 3.2.3 Непереводимые узлы (NON_TRANSLATABLE)

| Узел | Правило | Пример |
|------|---------|--------|
| `code_inline` | Inline код не переводится | `` `code` `` |
| `fence` | Fenced code block не переводится | ```python\ncode\n``` |
| `code_block` | Indented code block не переводится | 4 пробела + код |
| `math_inline` | Inline математика не переводится | `$x + y$` |
| `math_block` | Блочная математика не переводится | `$$x + y$$` |
| `html_inline` | Inline HTML не переводится | `<span>` |
| `html_block` | HTML блок не переводится | `<div>` |
| `hr` | Горизонтальная линия не переводится | `---` |
| `softbreak` | Мягкий перенос не переводится | `\n` |
| `hardbreak` | Жесткий перенос не переводится | `<br>` |

#### 3.2.4 Структурные узлы (STRUCTURAL)

| Узел | Правило | Пример |
|------|---------|--------|
| `bullet_list` | Структура списка сохраняется | `- item` |
| `ordered_list` | Структура списка сохраняется | `1. item` |
| `list_item` | Структура элемента сохраняется | - |
| `blockquote` | Структура цитаты сохраняется | `> text` |
| `table` | Структура таблицы сохраняется | `| a | b |` |
| `thead` | Структура шапки сохраняется | - |
| `tbody` | Структура тела сохраняется | - |
| `tr` | Структура строки сохраняется | - |
| `dl` | Структура списка определений сохраняется | - |

#### 3.2.5 Специальные узлы

| Узел | Правило | Пример |
|------|---------|--------|
| `tasklist_item` | Переводится текст, статус задачи сохраняется | `- [x] done` |
| `footnote_ref` | Маркер сноски не переводится | `[^1]` |
| `footnote_block` | Блок сносок сохраняется | - |

---

## 4. Извлечение текста с плейсхолдерами

### 4.1 Формат плейсхолдеров

```
{placeholder_type:placeholder_id:content}
```

**Примеры:**
- `{code:1:def hello():}` - inline код
- `{math:2:x + y = z}` - математика
- `{link:3:https://example.com}` - ссылка
- `{image:4:https://example.com/img.png}` - изображение
- `{html:5:<span class="test">}` - HTML

### 4.2 Генерация уникальных ID

```python
class PlaceholderManager:
    """Управляет плейсхолдерами и их ID."""
    
    def __init__(self):
        self.counter: Dict[str, int] = {}
        self.placeholders: Dict[str, Placeholder] = {}
    
    def generate_id(self, placeholder_type: str) -> str:
        """Генерирует уникальный ID для плейсхолдера."""
        if placeholder_type not in self.counter:
            self.counter[placeholder_type] = 0
        
        self.counter[placeholder_type] += 1
        return f"{placeholder_type}_{self.counter[placeholder_type]}"
    
    def create_placeholder(self, node: SyntaxTreeNode) -> Placeholder:
        """Создает плейсхолдер из узла AST."""
        placeholder_type = self._get_placeholder_type(node)
        placeholder_id = self.generate_id(placeholder_type)
        
        placeholder = Placeholder(
            id=placeholder_id,
            type=placeholder_type,
            original_content=self._extract_content(node),
            node_type=node.type,
            attrs=node.attrs.copy() if node.attrs else None,
            tag=node.tag,
            info=node.info
        )
        
        self.placeholders[placeholder_id] = placeholder
        return placeholder
    
    def _get_placeholder_type(self, node: SyntaxTreeNode) -> str:
        """Определяет тип плейсхолдера по типу узла."""
        type_map = {
            "code_inline": "code",
            "fence": "code",
            "code_block": "code",
            "math_inline": "math",
            "math_block": "math",
            "link_open": "link",
            "image": "image",
            "html_inline": "html",
            "html_block": "html",
        }
        return get_unit_type(node.type)
```

### 4.3 Извлечение текста из узла

```python
def extract_translatable_text(
    node: SyntaxTreeNode,
    placeholder_manager: PlaceholderManager
) -> str:
    """
    Извлекает переводимый текст из узла с заменой непереводимых частей на плейсхолдеры.
    
    Args:
        node: Узел AST
        placeholder_manager: Менеджер плейсхолдеров
        
    Returns:
        Текст с плейсхолдерами
    """
    if node.type == "text":
        return node.content
    
    elif node.type in ["code_inline", "fence", "code_block"]:
        placeholder = placeholder_manager.create_placeholder(node)
        return f"{{{placeholder.type}:{placeholder.id}}}"
    
    elif node.type in ["math_inline", "math_block"]:
        placeholder = placeholder_manager.create_placeholder(node)
        return f"{{{placeholder.type}:{placeholder.id}}}"
    
    elif node.type == "link_open":
        # Извлекаем текст ссылки, сохраняем URL как плейсхолдер
        text = ""
        for child in node.children or []:
            text += extract_translatable_text(child, placeholder_manager)
        
        placeholder = placeholder_manager.create_placeholder(node)
        return f"{{{placeholder.type}:{placeholder.id}:{text}}}"
    
    elif node.type == "image":
        # Переводим alt текст, сохраняем URL
        alt_text = node.attrs.get("alt", "") if node.attrs else ""
        placeholder = placeholder_manager.create_placeholder(node)
        return f"{{{placeholder.type}:{placeholder.id}:{alt_text}}}"
    
    elif node.type in ["html_inline", "html_block"]:
        placeholder = placeholder_manager.create_placeholder(node)
        return f"{{{placeholder.type}:{placeholder.id}}}"
    
    else:
        # Рекурсивно обрабатываем дочерние узлы
        text = ""
        for child in node.children or []:
            text += extract_translatable_text(child, placeholder_manager)
        return text
```

---

## 5. Алгоритм чанкования

### 5.1 Стратегия чанкования

```
┌─────────────────────────────────────────────────────────────┐
│                    Chunking Strategy                         │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Сбор всех TranslationUnit из AST                         │
│  2. Группировка по структурным границам:                     │
│     - Заголовки (heading)                                     │
│     - Блоки кода (code block)                                 │
│     - Таблицы (table)                                         │
│     - Цитаты (blockquote)                                     │
│     - Списки (list)                                           │
│  3. Разбиение на чанки по лимиту токенов                     │
│  4. Сохранение иерархии и контекста                          │
│                                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Алгоритм

```python
@dataclass
class TranslationChunk:
    """Чанк текста для перевода."""
    
    chunk_id: str
    units: List[TranslationUnit]      # Единицы перевода в чанке
    text: str                          # Текст для перевода
    tokens: int                        # Количество токенов
    context: Dict[str, Any]            # Контекст (заголовки, родители)
    boundaries: ChunkBoundaries        # Границы чанка

@dataclass
class ChunkBoundaries:
    """Границы чанка для сохранения структуры."""
    
    starts_with_heading: bool = False
    ends_with_heading: bool = False
    in_list: bool = False
    in_table: bool = False
    in_blockquote: bool = False
    list_level: int = 0
    table_row: Optional[int] = None
    table_col: Optional[int] = None

def create_chunks(
    units: List[TranslationUnit],
    max_tokens: int = 512,
    tokenizer: Any = None
) -> List[TranslationChunk]:
    """
    Создает чанки из единиц перевода.
    
    Args:
        units: Список единиц перевода
        max_tokens: Максимальное количество токенов в чанке
        tokenizer: Токенизатор для подсчета токенов
        
    Returns:
        Список чанков
    """
    chunks: List[TranslationChunk] = []
    current_chunk_units: List[TranslationUnit] = []
    current_text = ""
    current_tokens = 0
    
    for unit in units:
        # Подсчитываем токены для текущей единицы
        unit_tokens = count_tokens(unit.extracted_text, tokenizer)
        
        # Проверяем, нужно ли создать новый чанк
        would_exceed_limit = current_tokens + unit_tokens > max_tokens
        is_boundary = _is_strong_boundary(unit)
        
        if (current_chunk_units and (would_exceed_limit or is_boundary)):
            # Создаем чанк
            chunk = TranslationChunk(
                chunk_id=f"chunk_{len(chunks) + 1}",
                units=current_chunk_units.copy(),
                text=current_text.strip(),
                tokens=current_tokens,
                context=_build_context(current_chunk_units),
                boundaries=_detect_boundaries(current_chunk_units)
            )
            chunks.append(chunk)
            
            # Сбрасываем текущий чанк
            current_chunk_units = []
            current_text = ""
            current_tokens = 0
        
        # Добавляем единицу в текущий чанк
        current_chunk_units.append(unit)
        current_text += unit.extracted_text + " "
        current_tokens += unit_tokens
    
    # Добавляем последний чанк
    if current_chunk_units:
        chunk = TranslationChunk(
            chunk_id=f"chunk_{len(chunks) + 1}",
            units=current_chunk_units,
            text=current_text.strip(),
            tokens=current_tokens,
            context=_build_context(current_chunk_units),
            boundaries=_detect_boundaries(current_chunk_units)
        )
        chunks.append(chunk)
    
    return chunks

def _is_strong_boundary(unit: TranslationUnit) -> bool:
    """Проверяет, является ли узел сильной границей для чанкования."""
    strong_boundaries = [
        "heading_open",
        "table_open",
        "fence",
        "code_block",
        "blockquote_open",
        "bullet_list_open",
        "ordered_list_open"
    ]
    return unit.node_type in strong_boundaries

def _build_context(units: List[TranslationUnit]) -> Dict[str, Any]:
    """Собирает контекст для чанка (текущие заголовки, родители)."""
    context = {
        "current_headings": [],
        "parent_types": [],
        "list_level": 0
    }
    
    for unit in units:
        if unit.node_type.startswith("heading"):
            level = int(unit.node_type.split("_")[1])
            context["current_headings"].append({
                "level": level,
                "text": unit.extracted_text
            })
        
        if unit.node_type in ["bullet_list_open", "ordered_list_open"]:
            context["list_level"] += 1
    
    return context

def _detect_boundaries(units: List[TranslationUnit]) -> ChunkBoundaries:
    """Определяет границы чанка."""
    boundaries = ChunkBoundaries()
    
    if units:
        first_unit = units[0]
        last_unit = units[-1]
        
        boundaries.starts_with_heading = first_unit.node_type.startswith("heading")
        boundaries.ends_with_heading = last_unit.node_type.startswith("heading")
        boundaries.in_list = any(
            u.node_type in ["bullet_list_open", "ordered_list_open"]
            for u in units
        )
        boundaries.in_table = any(
            u.node_type.startswith("table") or u.node_type.startswith("tr")
            for u in units
        )
        boundaries.in_blockquote = any(
            u.node_type.startswith("blockquote")
            for u in units
        )
    
    return boundaries
```

---

## 6. Восстановление AST

### 6.1 Процесс восстановления

```
┌─────────────────────────────────────────────────────────────┐
│                  AST Reconstruction Process                   │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Загрузка оригинального AST                                │
│  2. Замена текста в узлах на переведенный                     │
│  3. Восстановление плейсхолдеров                              │
│  4. Сохранение структуры и атрибутов                          │
│  5. Валидация AST                                             │
│  6. Рендеринг в Markdown                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Алгоритм восстановления

```python
def reconstruct_ast(
    original_ast: SyntaxTreeNode,
    translated_units: Dict[str, TranslationUnit],
    placeholder_manager: PlaceholderManager
) -> SyntaxTreeNode:
    """
    Восстанавливает AST с переведенным текстом.
    
    Args:
        original_ast: Оригинальное AST
        translated_units: Словарь переведенных единиц {node_id: unit}
        placeholder_manager: Менеджер плейсхолдеров
        
    Returns:
        Восстановленное AST
    """
    # Создаем копию AST для модификации
    new_ast = deepcopy(original_ast)
    
    # Рекурсивно обходим и заменяем текст
    _replace_text_in_ast(new_ast, translated_units, placeholder_manager)
    
    return new_ast

def _replace_text_in_ast(
    node: SyntaxTreeNode,
    translated_units: Dict[str, TranslationUnit],
    placeholder_manager: PlaceholderManager
):
    """Рекурсивно заменяет текст в узлах AST."""
    
    # Проверяем, есть ли переведенный текст для этого узла
    if node.type == "text" and hasattr(node, "node_id"):
        unit = translated_units.get(node.node_id)
        if unit and unit.translated_text:
            # Восстанавливаем плейсхолдеры в переведенном тексте
            restored_text = _restore_placeholders(
                unit.translated_text,
                placeholder_manager
            )
            node.content = restored_text
    
    # Рекурсивно обрабатываем дочерние узлы
    for child in node.children or []:
        _replace_text_in_ast(child, translated_units, placeholder_manager)

def _restore_placeholders(
    text: str,
    placeholder_manager: PlaceholderManager
) -> str:
    """
    Восстанавливает плейсхолдеры в тексте.
    
    Args:
        text: Текст с плейсхолдерами
        placeholder_manager: Менеджер плейсхолдеров
        
    Returns:
        Текст с восстановленными плейсхолдерами
    """
    # Регулярное выражение для поиска плейсхолдеров
    placeholder_pattern = r"\{(\w+):([^}:]+)(?::([^}]+))?\}"
    
    def replace_match(match):
        placeholder_type = match.group(1)
        placeholder_id = match.group(2)
        content = match.group(3) if match.group(3) else ""
        
        placeholder = placeholder_manager.placeholders.get(placeholder_id)
        if not placeholder:
            return match.group(0)  # Возвращаем оригинальный плейсхолдер
        
        # Восстанавливаем оригинальный контент
        return placeholder.original_content
    
    return re.sub(placeholder_pattern, replace_match, text)
```

### 6.3 Рендеринг в Markdown

```python
def render_ast_to_markdown(ast: SyntaxTreeNode) -> str:
    """
    Рендерит AST обратно в Markdown.
    
    Args:
        ast: AST для рендеринга
        
    Returns:
        Markdown строка
    """
    # Используем markdown-it-py для рендеринга
    from markdown_it import MarkdownIt
    
    md = MarkdownIt("commonmark")
    tokens = _ast_to_tokens(ast)
    return md.renderer.render(tokens, md.options, {})

def _ast_to_tokens(node: SyntaxTreeNode) -> List[Any]:
    """Конвертирует AST обратно в токены."""
    tokens = []
    
    # Создаем токен для текущего узла
    token = _create_token_from_node(node)
    tokens.append(token)
    
    # Добавляем дочерние токены
    for child in node.children or []:
        tokens.extend(_ast_to_tokens(child))
    
    # Добавляем закрывающий токен для парных узлов
    if node.type.endswith("_open"):
        close_type = node.type.replace("_open", "_close")
        close_token = _create_closing_token(close_type)
        tokens.append(close_token)
    
    return tokens
```

---

## 7. Обработка edge cases

### 7.1 Вложенные ссылки и изображения

**Проблема:** Markdown не поддерживает вложенные ссылки, но изображения могут быть внутри ссылок.

**Решение:**
```python
# ![alt](image.png) внутри [text](url)
# Обрабатываем как отдельные плейсхолдеры
"{link:1:{image:2:alt text} link text}"
```

### 7.2 Экранированные символы

**Проблема:** Экранированные символы (`\*`, `\#`) не должны обрабатываться как разметка.

**Решение:**
```python
def handle_escaped_chars(text: str) -> str:
    """Обрабатывает экранированные символы."""
    # Сохраняем экранированные символы как плейсхолдеры
    text = re.sub(r"\\([*_`{}\[\]()#+\-.!])", r"{escape:\1}", text)
    return text
```

### 7.3 Многоязычный контент

**Проблема:** Документ может содержать текст на разных языках.

**Решение:**
```python
def detect_language_mix(text: str) -> List[str]:
    """Определяет языки в тексте."""
    # Используем библиотеку для определения языка
    from langdetect import detect_langs
    
    try:
        langs = detect_langs(text)
        return [lang.lang for lang in langs if lang.prob > 0.3]
    except:
        return []
```

### 7.4 Длинные слова и URL

**Проблема:** Длинные слова (URL, email) могут превышать лимит токенов.

**Решение:**
```python
def split_long_tokens(text: str, max_length: int = 100) -> str:
    """Разбивает длинные токены на части."""
    words = text.split()
    result = []
    
    for word in words:
        if len(word) > max_length:
            # Разбиваем длинное слово
            parts = [word[i:i+max_length] for i in range(0, len(word), max_length)]
            result.extend(parts)
        else:
            result.append(word)
    
    return " ".join(result)
```

### 7.5 Математические формулы с текстом

**Проблема:** Формулы могут содержать текстовые пояснения.

**Решение:**
```python
# $E = mc^2$ where $E$ is energy
# Переводим только текстовые части
"{math:1:E = mc^2} where {math:2:E} is energy"
```

### 7.6 Ссылки с title

**Проблема:** Ссылки могут иметь title атрибут.

**Решение:**
```python
# [text](url "title")
# Переводим text и title, сохраняем url
"{link:1:url:text:title}"
```

### 7.7 Вложенные списки

**Проблема:** Вложенные списки должны сохранять уровень вложенности.

**Решение:**
```python
def preserve_list_nesting(node: SyntaxTreeNode, level: int = 0):
    """Сохраняет уровень вложенности списков."""
    if node.type in ["bullet_list_open", "ordered_list_open"]:
        level += 1
    
    # Сохраняем уровень в метаданных узла
    node.list_level = level
    
    for child in node.children or []:
        preserve_list_nesting(child, level)
```

### 7.8 Таблицы с многострочными ячейками

**Проблема:** Ячейки таблиц могут содержать несколько строк.

**Решение:**
```python
def handle_multiline_table_cells(cell_content: str) -> str:
    """Обрабатывает многострочные ячейки таблиц."""
    # Сохраняем переносы строк внутри ячеек
    cell_content = cell_content.replace("\n", "<br>")
    return cell_content
```

### 7.9 HTML внутри Markdown

**Проблема:** HTML может содержать Markdown-подобный текст.

**Решение:**
```python
def handle_html_content(node: SyntaxTreeNode):
    """Обрабатывает HTML контент."""
    if node.type in ["html_inline", "html_block"]:
        # Не парсим содержимое HTML как Markdown
        node.skip_parsing = True
```

### 7.10 Reference-style ссылки

**Проблема:** Reference-style ссылки `[text][id]` с определениями в конце.

**Решение:**
```python
# [text][id]
# Переводим только text, сохраняем id
"{link_ref:id:text}"

# [id]: url "title"
# Сохраняем как есть
```

---

## 8. Обработка ошибок и валидация

### 8.1 Типы ошибок

| Тип ошибки | Описание | Обработка |
|------------|----------|-----------|
| `ParseError` | Ошибка парсинга Markdown | Возвращаем оригинальный текст |
| `TranslationError` | Ошибка перевода | Пропускаем чанк, логируем |
| `PlaceholderMismatch` | Несоответствие плейсхолдеров | Восстанавливаем оригинальный текст |
| `TokenLimitExceeded` | Превышен лимит токенов | Разбиваем на меньшие чанки |
| `InvalidAST` | Невалидное AST | Валидируем перед рендерингом |

### 8.2 Валидация AST

```python
def validate_ast(ast: SyntaxTreeNode) -> List[str]:
    """
    Валидирует AST на корректность.
    
    Args:
        ast: AST для валидации
        
    Returns:
        Список ошибок (пустой если нет ошибок)
    """
    errors = []
    
    # Проверяем баланс открывающих/закрывающих тегов
    if not _check_tag_balance(ast):
        errors.append("Unbalanced tags in AST")
    
    # Проверяем вложенность списков
    if not _check_list_nesting(ast):
        errors.append("Invalid list nesting")
    
    # Проверяем структуру таблиц
    if not _check_table_structure(ast):
        errors.append("Invalid table structure")
    
    return errors

def _check_tag_balance(node: SyntaxTreeNode) -> bool:
    """Проверяет баланс открывающих/закрывающих тегов."""
    open_tags = []
    
    def check_node(n: SyntaxTreeNode):
        if n.type.endswith("_open"):
            open_tags.append(n.type)
        elif n.type.endswith("_close"):
            if not open_tags:
                return False
            open_tags.pop()
        return True
    
    # Обходим все узлы
    for child in node.walk():
        if not check_node(child):
            return False
    
    return len(open_tags) == 0
```

### 8.3 Обработка ошибок перевода

```python
class TranslationErrorManager:
    """Управляет ошибками перевода."""
    
    def __init__(self):
        self.errors: List[TranslationError] = []
        self.error_counts: Dict[str, int] = {}
    
    def handle_error(
        self,
        error: Exception,
        unit: Optional[TranslationUnit] = None,
        chunk: Optional[TranslationChunk] = None
    ):
        """Обрабатывает ошибку перевода."""
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        translation_error = TranslationError(
            error_type=error_type,
            message=str(error),
            unit_id=unit.node_id if unit else None,
            chunk_id=chunk.chunk_id if chunk else None,
            timestamp=datetime.now()
        )
        
        self.errors.append(translation_error)
        
        # Логируем ошибку
        logger.error(f"Translation error: {error_type} - {error}")
        
        # Решение в зависимости от типа ошибки
        if error_type == "TokenLimitExceeded":
            self._handle_token_limit_error(unit)
        elif error_type == "PlaceholderMismatch":
            self._handle_placeholder_mismatch(unit)
        else:
            self._handle_generic_error(unit)
    
    def _handle_token_limit_error(self, unit: TranslationUnit):
        """Обрабатывает ошибку превышения лимита токенов."""
        # Разбиваем единицу на меньшие части
        pass
    
    def _handle_placeholder_mismatch(self, unit: TranslationUnit):
        """Обрабатывает ошибку несоответствия плейсхолдеров."""
        # Восстанавливаем оригинальный текст
        unit.translated_text = unit.original_text
        unit.has_errors = True
    
    def _handle_generic_error(self, unit: TranslationUnit):
        """Обрабатывает общую ошибку."""
        # Пропускаем перевод, сохраняем оригинальный текст
        if unit:
            unit.translated_text = unit.original_text
            unit.has_errors = True
```

---

## 9. Производительность и оптимизация

### 9.1 Кэширование

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def parse_markdown_cached(markdown_text: str) -> SyntaxTreeNode:
    """Кэширует результат парсинга Markdown."""
    md = create_markdown_parser()
    tokens = md.parse(markdown_text)
    return SyntaxTreeNode(tokens)
```

### 9.2 Параллельный перевод

```python
from concurrent.futures import ThreadPoolExecutor

def translate_chunks_parallel(
    chunks: List[TranslationChunk],
    translator: Any,
    max_workers: int = 4
) -> Dict[str, str]:
    """Переводит чанки параллельно."""
    
    def translate_chunk(chunk: TranslationChunk) -> tuple:
        translated_text = translator.translate(chunk.text)
        return (chunk.chunk_id, translated_text)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(translate_chunk, chunks)
    
    return dict(results)
```

### 9.3 Пакетная обработка

```python
def batch_translate(
    documents: List[str],
    batch_size: int = 10
) -> List[str]:
    """Переводит документы пакетами."""
    translated_docs = []
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        # Параллельный перевод батча
        batch_results = translate_chunks_parallel(batch)
        translated_docs.extend(batch_results)
    
    return translated_docs
```

---

## 10. Тестирование

### 10.1 Тестовые сценарии

| Сценарий | Описание | Ожидаемый результат |
|----------|----------|---------------------|
| `headings` | Заголовки с форматированием | Уровни сохранены, текст переведен |
| `tables` | Таблицы с кодом и ссылками | Структура сохранена, код не переведен |
| `links` | Ссылки с title | URL сохранен, текст переведен |
| `fenced-code` | Fenced code blocks | Код сохранен как есть |
| `images` | Изображения с alt | URL сохранен, alt переведен |
| `html-blocks` | HTML блоки | HTML сохранен как есть |
| `inline-html` | Inline HTML | HTML сохранен как есть |
| `nested-lists` | Вложенные списки | Уровни вложенности сохранены |
| `mixed-formatting` | Смешанное форматирование | Все форматирование сохранено |
| `escaped-markdown` | Экранированный Markdown | Экранирование сохранено |
| `malformed-markdown` | Невалидный Markdown | Обработка без падения |
| `yaml-frontmatter` | YAML frontmatter | Ключи сохранены, значения переведены |
| `math-expressions` | Математические формулы | Формулы сохранены как есть |
| `footnotes` | Сноски | Маркеры сохранены, текст переведен |
| `reference-links` | Reference-style ссылки | ID сохранены, текст переведен |
| `rtl-languages` | RTL языки | Направление текста сохранено |
| `huge-documents` | Большие документы | Разбивка на чанки работает |
| `unicode-punctuation` | Unicode пунктуация | Пунктуация сохранена |
| `softbreak-hardbreak` | Переносы строк | Тип переноса сохранен |
| `task-lists` | Списки задач | Статус задач сохранен |
| `definition-lists` | Списки определений | Структура сохранена |

### 10.2 Правила валидации

```json
{
  "preserve_heading_levels": true,
  "preserve_inline_formatting": true,
  "preserve_links": true,
  "preserve_href": true,
  "preserve_link_titles": true,
  "preserve_inline_code": true,
  "preserve_fence_language": true,
  "preserve_code_exactly": true,
  "preserve_tables": true,
  "preserve_table_dimensions": true,
  "preserve_html_blocks": true,
  "preserve_raw_html": true,
  "preserve_inline_html": true,
  "preserve_list_structure": true,
  "preserve_list_nesting": true,
  "preserve_ordered_lists": true,
  "preserve_escapes": true,
  "handle_malformed_input": true,
  "parse_yaml_frontmatter": true,
  "translate_yaml_values": true,
  "preserve_yaml_structure": true,
  "preserve_math": true,
  "preserve_footnote_markers": true,
  "translate_footnote_content": true,
  "maintain_footnote_order": true,
  "compare_ast_structure": true,
  "strict_text_equality": false
}
```

---

## 11. Примеры использования

### 11.1 Базовый перевод

```python
from markdown_translator import MarkdownTranslator

translator = MarkdownTranslator(
    source_lang="eng_Latn",
    target_lang="rus_Cyrl"
)

markdown_input = """
# Hello World

This is **bold** text with `code`.

- Item 1
- Item 2
"""

translated = translator.translate(markdown_input)
print(translated)
```

### 11.2 Перевод с кастомными плагинами

```python
from markdown_translator import MarkdownTranslator
from mdit_py_plugins import custom_plugin

translator = MarkdownTranslator(
    source_lang="eng_Latn",
    target_lang="rus_Cyrl",
    custom_plugins=[custom_plugin]
)

translated = translator.translate(markdown_input)
```

### 11.3 Пакетный перевод

```python
documents = [
    "# Doc 1\nContent 1",
    "# Doc 2\nContent 2",
    "# Doc 3\nContent 3"
]

translated_docs = translator.batch_translate(documents)
```

---

## 12. Заключение

Система перевода Markdown с сохранением форматирования обеспечивает:

1. **Полное сохранение структуры** - все элементы Markdown сохраняют свою структуру
2. **Интеллектуальное чанкование** - разбиение на чанки с учетом границ и контекста
3. **Управление плейсхолдерами** - надежная система замены непереводимых элементов
4. **Обработка edge cases** - поддержка сложных сценариев и ошибок
5. **Расширяемость** - поддержка кастомных плагинов и правил
6. **Производительность** - кэширование, параллельная обработка, пакетная обработка

Система готова к интеграции в существующий NLLB сервер и может быть расширена для поддержки дополнительных форматов и сценариев использования.
