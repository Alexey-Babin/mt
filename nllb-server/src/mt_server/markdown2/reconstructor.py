from typing import Any, Dict, List, Tuple

import regex as re

from .translation_unit import TranslationUnit
from .translation_unit_type import TranslationUnitType


class MarkdownReconstructor:
    """Конечный автомат (State Machine) для обратной сборки Markdown-документа.

    Линейно обходит плоский список TranslationUnit, восстанавливает структуру
    вложенности (через стек блоков) и разворачивает плейсхолдеры в инлайнах.
    """

    def __init__(self):
        self._buffer: List[str] = []

        # Стек теперь хранит словари с метаданными блоков:
        # {"type": "blockquote"|"list"|"list_item", "marker": "-"|"1.", "is_first_paragraph": True}
        self._block_stack: List[Dict[str, Any]] = []

    def reconstruct(self, units: List[TranslationUnit]) -> str:
        """Главный метод сборщика.

        Принимает плоский упорядоченный список юнитов и возвращает монолитную
        строку готового отформатированного Markdown-документа.
        """
        self._buffer = []
        self._block_stack = []

        for unit in units:
            if unit.unit_type == TranslationUnitType.STRUCTURAL_IGNORE:
                self._handle_structural_marker(unit)

            elif unit.unit_type == TranslationUnitType.CONTEXT_BLOCK:
                self._handle_context_block(unit)

            elif unit.unit_type == TranslationUnitType.SPECIAL_CASE:
                self._handle_special_case(unit)

        return "".join(self._buffer)

    def _get_current_prefix(self, for_block_start: bool = False) -> Tuple[str, str]:
        """Вычисляет префикс для текущей строки на основе стека вложенности.

        Расширен поддержкой списков определений (dt/dd).
        """
        line_prefix = ""
        item_marker = ""
        list_level = 0

        for block in self._block_stack:
            b_type = block["type"]

            if b_type == "blockquote":
                line_prefix += "> "

            elif b_type in ("bullet_list", "ordered_list"):
                if list_level > 0:
                    line_prefix += "    "
                list_level += 1

            elif b_type == "list_item":
                if for_block_start and block.get("is_first_paragraph", False):
                    item_marker = f"{block['marker']} "
                    block["is_first_paragraph"] = False
                elif not for_block_start:
                    line_prefix += " " * (len(block["marker"]) + 1)

            # --- ПОДДЕРЖКА СПИСКОВ ОПРЕДЕЛЕНИЙ ---
            elif b_type == "dd":
                if for_block_start and block.get("is_first_line", False):
                    item_marker = ": "
                    block["is_first_line"] = False
                elif not for_block_start:
                    # Последующие строки блока dd получают отступ в 2 пробела (длина ": ")
                    line_prefix += "  "

        return line_prefix, item_marker

    def _write_with_prefix(self, text: str):
        """Записывает текст в буфер, динамически рассчитывая отступы списков и цитат."""
        # Получаем префиксы для СТАРТА блока текста (первой строки)
        line_prefix, item_marker = self._get_current_prefix(for_block_start=True)

        # Сборка стартовой строки с учетом маркера списка (если он есть)
        start_prefix = line_prefix + item_marker

        if not self._buffer or self._buffer[-1].endswith("\n"):
            self._buffer.append(start_prefix)

        # Для последующих строк (если текст многострочный) маркер списка не нужен,
        # используются только стандартные отступы line_prefix
        multi_prefix, _ = self._get_current_prefix(for_block_start=False)

        # Модифицируем внутренние переносы строк
        processed_text = text.replace("\n", f"\n{multi_prefix}")

        if processed_text.endswith(f"\n{multi_prefix}"):
            processed_text = processed_text[: -len(multi_prefix)]

        self._buffer.append(processed_text)

    def _handle_structural_marker(self, unit: TranslationUnit):
        """Обрабатывает маркеры каркаса документа (цитаты, списки, таблицы, fence)."""
        is_open = unit.node_type.endswith("_open")
        is_close = unit.node_type.endswith("_close")
        base_type = unit.node_type.replace("_open", "").replace("_close", "")

        # Хронологический перехват блоков кода (fence, code_block) и разделителей (hr)
        # Обрабатываем их строго ОДИН раз (при открытии или если это одиночный токен hr)
        if base_type in ("fence", "code_block"):
            if is_open or (not is_open and not is_close):
                # 1. Перед блоком кода выставляем текущий префикс вложенности (> ),
                # чтобы сам маркер открытия ``` встал на правильный уровень структуры цитаты
                prefix, _ = self._get_current_prefix(for_block_start=False)
                if prefix and (not self._buffer or self._buffer[-1].endswith("\n")):
                    self._buffer.append(prefix)

                # 2. Пишем сам блок кода НАПРЯМУЮ в буфер.
                # Это гарантирует, что внутренние строки кода останутся чистыми и без префиксов '> '.
                info_str = unit.info or ""
                code_content = f"```{info_str}\n{unit.original_text}```\n\n"
                self._buffer.append(code_content)
            return  # Игнорируем fence_close, предотвращая засорение стека блоков

        if unit.node_type == "hr":
            self._write_with_prefix("---\n\n")
            return

        # --- СТАНДАРТНАЯ СТРУКТУРНАЯ ЛОГИКА ДЛЯ ПАРНЫХ КОНТЕЙНЕРОВ (цитаты, списки) ---
        if is_open:
            marker = "-"
            if base_type == "ordered_list":
                start_num = unit.attrs.get("start", 1) if unit.attrs else 1
                marker = f"{start_num}."
            elif base_type == "bullet_list":
                if unit.info and unit.info in ("-", "*", "+"):
                    marker = unit.info
                elif unit.tag and unit.tag in ("-", "*", "+"):
                    marker = unit.tag
            elif base_type == "list_item":
                # Элемент списка наследует маркер от своего родительского контейнера в стеке
                parent_list = next(
                    (
                        b
                        for b in reversed(self._block_stack)
                        if b["type"] in ("bullet_list", "ordered_list")
                    ),
                    None,
                )
                if parent_list:
                    marker = parent_list["marker"]

            # Пушим в стек расширенные метаданные
            self._block_stack.append(
                {
                    "type": base_type,
                    "marker": marker,
                    "is_first_paragraph": True if base_type == "list_item" else False,
                }
            )

        elif is_close:
            # Безопасно снимаем блок со стека
            if self._block_stack and self._block_stack[-1]["type"] == base_type:
                self._block_stack.pop()

            if base_type in (
                "blockquote",
                "bullet_list",
                "ordered_list",
                "table",
                "dl",
            ):
                if self._buffer and not self._buffer[-1].endswith("\n"):
                    self._buffer.append("\n")

    def _handle_special_case(self, unit: TranslationUnit):
        """Обрабатывает узлы метаданных Front Matter.

        Восстанавливает технический блок метаданных в начале документа,
        оборачивая его контент в стандартные ограничители '---'.
        """
        if unit.node_type == "front_matter":
            # Извлекаем текст метаданных.
            # Если в будущем у юнита заполнится translated_text (после кастомного yaml-парсера),
            # мы возьмем его, иначе возвращаем исходную original_text.
            fm_content = (
                unit.translated_text if unit.translated_text else unit.original_text
            )

            # Убеждаемся, что контент заканчивается на перевод строки для красивого форматирования
            if fm_content and not fm_content.endswith("\n"):
                fm_content += "\n"

            # Формируем валидный блок Front Matter
            # Метаданные всегда находятся на самом верхнем уровне документа,
            # поэтому пишем их напрямую в буфер, минуя префиксы вложенности.
            front_matter_block = f"---\n{fm_content}---\n\n"
            self._buffer.append(front_matter_block)

    def _handle_context_block(self, unit: TranslationUnit):
        """Обрабатывает текстовые контейнеры (включая dt и dd)."""
        is_close = unit.node_type.endswith("_close")
        base_type = unit.node_type.replace("_open", "").replace("_close", "")

        if is_close:
            # Снимаем контекстный блок dt/dd со стека
            if self._block_stack and self._block_stack[-1]["type"] == base_type:
                self._block_stack.pop()

            if base_type in (
                "paragraph",
                "heading",
                "field_name",
                "field_body",
                "dt",
                "dd",
            ):
                if self._buffer and not self._buffer[-1].endswith("\n"):
                    self._buffer.append("\n")
            return

        # ИСПРАВЛЕНО: Избыточный блок взведения флага is_first_paragraph удален!

        # Узлы dt и dd сами являются открывающими контекстными блоками.
        # Пушим их в стек, чтобы метод префиксации знал, как их форматировать.
        if base_type in ("dt", "dd"):
            self._block_stack.append({"type": base_type, "is_first_line": True})

        text_to_restore = (
            unit.translated_text
            if unit.translated_text is not None
            else unit.extracted_text
        )
        restored_markdown = self._restore_inline_placeholders(text_to_restore, unit)

        if unit.node_type == "heading":
            level = unit.level if unit.level else 1
            block_content = "#" * level + " " + restored_markdown
        else:
            block_content = restored_markdown

        self._write_with_prefix(block_content)

    def _restore_inline_placeholders(self, text: str, unit: TranslationUnit) -> str:
        """Разворачивает маски плейсхолдеров обратно в Markdown разметку.

        Использует парные регулярные выражения для предотвращения ломания синтаксиса.
        """
        if not unit.placeholders:
            return text

        # Нормализуем текст ответа: убираем возможные фантомные пробелы вокруг масок,
        # которые могла добавить модель NLLB, приводя их к стандартному виду "{lnk_1}"
        normalized_text = text
        for ph in unit.placeholders:
            # Очищаем маску (например, из " {lnk_1} " делаем "{lnk_1}")
            clean_mask = ph.tag_mask.strip()
            # Находим в тексте маску с любым количеством пробелов вокруг неё и сжимаем отступы
            normalized_text = re.sub(
                r"\s*\{\s*" + re.escape(clean_mask[1:-1]) + r"\s*\}\s*",
                f" {clean_mask} ",
                normalized_text,
            )

        # Строим быстрые карты доступа к плейсхолдерам по их числовым ID и типам
        open_ph_map = {}
        atomic_ph_map = {}
        for ph in unit.placeholders:
            clean_mask = ph.tag_mask.strip()
            if ph.is_closing:
                continue

            # Извлекаем числовой ID из маски (например, из "{lnk_1}" вытаскиваем 1)
            if match := re.search(r"\d+", clean_mask):
                ph_id = int(match.group())
                prefix = clean_mask[1:-1].split("_")[0]
                if ph.node_type.endswith("_open"):
                    open_ph_map[(prefix, ph_id)] = ph
                else:
                    atomic_ph_map[clean_mask] = ph

        # --- ШАГ 1: ВОССТАНОВЛЕНИЕ ПАРНЫХ ТЕГОВ (Ссылки и Стили) ---
        # Регулярка находит: {префикс_ID} текст {/префикс_ID}
        # Учитывает любые пробелы внутри фигурных скобок
        paired_regex = re.compile(
            r"\{\s*([a-zA-Z]+)_(\d+)\s*\}(.*?)\{\s*/\1_\2\s*\}", re.DOTALL
        )

        def replace_paired(match):
            prefix = match.group(1)
            ph_id = int(match.group(2))
            inner_content = match.group(3).strip()

            ph = open_ph_map.get((prefix, ph_id))
            if not ph:
                return match.group(0)  # Фолбек: возвращаем как есть, если тег сломан

            if prefix == "lnk":
                href = ph.original_markup.get("href", "")
                title = f' "{t}"' if (t := ph.original_markup.get("title")) else ""
                return f"[{inner_content}]({href}{title})"

            elif prefix == "s":
                return f"**{inner_content}**"
            elif prefix == "e":
                return f"*{inner_content}*"
            elif prefix == "del":
                return f"~~{inner_content}~~"

            return inner_content

        # Запускаем рекурсивную замену для поддержки вложенных инлайнов (например, жирный внутри ссылки)
        old_text = ""
        while old_text != normalized_text:
            old_text = normalized_text
            normalized_text = paired_regex.sub(replace_paired, normalized_text)

        # --- ШАГ 2: ВОССТАНОВЛЕНИЕ ОДИНОЧНЫХ ТЕГОВ (Код, Картинки, Брейки) ---
        atomic_regex = re.compile(r"\{\s*([a-zA-Z0-9_/]+)\s*\}")

        def replace_atomic(match):
            full_mask = f"{{{match.group(1)}}}"
            ph = atomic_ph_map.get(full_mask)
            if not ph:
                return full_mask

            if ph.node_type == "code_inline":
                return (
                    f"`{ph.original_markup}`"
                    if not str(ph.original_markup).startswith("`")
                    else str(ph.original_markup)
                )
            elif ph.node_type == "math_inline":
                return (
                    f"${ph.original_markup}$"
                    if not str(ph.original_markup).startswith("$")
                    else str(ph.original_markup)
                )
            elif ph.node_type in ("softbreak", "hardbreak"):
                return "\n" if ph.node_type == "softbreak" else "<br>"
            elif ph.node_type == "image":
                src = ph.original_markup.get("src", "")
                title = f' "{t}"' if (t := ph.original_markup.get("title")) else ""
                # Если в original_markup нет alt (например в моках), берем оригинальный из юнита
                alt = ph.original_markup.get("alt", "") or unit.original_text or "image"
                return f"![{alt}]({src}{title})"

            return str(ph.original_markup)

        final_text = atomic_regex.sub(replace_atomic, normalized_text)

        # Чистим артефакты двойных пробелов, возникшие при нормализации масок
        return re.sub(r" +", " ", final_text).strip()
