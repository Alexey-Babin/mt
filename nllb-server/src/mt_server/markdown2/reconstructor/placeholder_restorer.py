"""Модуль восстановления плейсхолдеров в Markdown-разметке.

Отвечает за:
- Нормализацию текста (очистка пробелов вокруг масок)
- Восстановление парных тегов (ссылки, strong, em, del)
- Восстановление атомарных тегов (code_inline, math_inline, image, breaks)

Формат плейсхолдеров (dunder):
- Парные: __X_O_N__ ... __X_C_N__ (например, __B_O_1__ ... __B_C_1__)
- Атомарные: __X_N__ (например, __C_1__)
"""

import logging
from typing import Dict, List, Tuple

import regex as re

from ..models.placeholder import Placeholder
from ..models.placeholder_codes import PAIRED_CODES, SINGLE_TRANSLATE_CODES, PROTECT_CODES
from ..models.translation_unit import TranslationUnit

logger = logging.getLogger("uvicorn.error")


class PlaceholderRestorer:
    """Восстанавливает плейсхолдеры обратно в Markdown-разметку."""

    # Regex для парных тегов: __X_O_N__ ... __X_C_N__
    PAIRED_REGEX = re.compile(r"__([A-Z])_O_(\d+)__(.*?)__\1_C_\2__", re.DOTALL)
    
    # Regex для атомарных тегов: __X_N__
    ATOMIC_REGEX = re.compile(r"__([A-Z])_(\d+)__")

    def __init__(self):
        self._open_ph_map: Dict[Tuple[str, int], Placeholder] = {}
        self._atomic_ph_map: Dict[str, Placeholder] = {}

    def reset(self):
        """Сбрасывает карты плейсхолдеров."""
        self._open_ph_map = {}
        self._atomic_ph_map = {}

    def build_placeholder_maps(self, placeholders: List[Placeholder]):
        """Строит быстрые карты доступа к плейсхолдерам по их ID и типам."""
        self.reset()

        for ph in placeholders:
            tag_mask = ph.tag_mask

            if ph.is_closing:
                # Закрывающие плейсхолдеры не добавляем в карты для поиска открывающих
                continue

            # Парсим tag_mask для извлечения кода и ID
            # Формат: __X_Y_N__ или __X_N__
            if match := re.match(r"__([A-Z])_(?:[OC]_)?(\d+)__", tag_mask):
                code = match.group(1)
                ph_id = int(match.group(2))

                # Определяем, является ли это парным тегом
                if code in PAIRED_CODES.values():
                    self._open_ph_map[(code, ph_id)] = ph
                # Атомарные теги
                elif code in SINGLE_TRANSLATE_CODES.values() or code in PROTECT_CODES.values():
                    self._atomic_ph_map[tag_mask] = ph

        logger.debug(
            "Placeholder maps built: open_tags=%d, atomic_tags=%d",
            len(self._open_ph_map),
            len(self._atomic_ph_map),
        )

    # Regex для удаления пробела между закрывающим/атомарным плейсхолдером и пунктуацией.
    # Пример: __L_C_1__ . → __L_C_1__.
    _PLACEHOLDER_PUNCTUATION_RE = re.compile(r"(__[A-Z](?:_[OC])?_\d+__)\s+([.,!?;:)])")

    def normalize_text(self, text: str, placeholders: List[Placeholder]) -> str:
        """Нормализует текст после NLLB.

        Плейсхолдеры уже отделены пробелами (добавлены на этапе AST-walk).
        Здесь убираем артефактные пробелы между плейсхолдерами и пунктуацией,
        которые NLLB могла сохранить из исходного текста.
        """
        normalized = self._PLACEHOLDER_PUNCTUATION_RE.sub(r"\1\2", text)
        # Схлопываем множественные пробелы
        normalized = re.sub(r"  +", " ", normalized)
        return normalized

    def restore(self, text: str, unit: TranslationUnit) -> str:
        """Разворачивает маски плейсхолдеров обратно в Markdown разметку.

        Использует парные регулярные выражения для предотвращения ломания синтаксиса.
        """
        if not unit.placeholders:
            logger.debug("No placeholders to restore for unit")
            return text

        logger.debug(
            "Starting placeholder restoration: total_placeholders=%d",
            len(unit.placeholders),
        )

        # Нормализуем текст ответа
        normalized_text = self.normalize_text(text, unit.placeholders)

        # Строим карты плейсхолдеров
        self.build_placeholder_maps(unit.placeholders)

        # Шаг 1: Восстановление парных тегов (ссылки и стили)
        normalized_text = self._restore_paired_tags(normalized_text, unit)

        # Шаг 2: Восстановление одиночных тегов (код, картинки, брейки)
        final_text = self._restore_atomic_tags(normalized_text, unit)

        # Чистим артефакты двойных пробелов, возникшие при нормализации масок
        clear_text = re.sub(r" +", " ", final_text).strip()
        logger.debug(
            "Placeholder restoration complete: original_length=%d, final_length=%d",
            len(text),
            len(clear_text),
        )
        return clear_text

    def _restore_paired_tags(self, text: str, unit: TranslationUnit) -> str:
        """Восстанавливает парные теги (ссылки, strong, em, del)."""
        
        def replace_paired(match):
            code = match.group(1)  # Однобуквенный код (B, I, L, D)
            ph_id = int(match.group(2))
            inner_content = match.group(3).strip()

            ph = self._open_ph_map.get((code, ph_id))
            if not ph:
                logger.warning(
                    "Paired placeholder not found in map: code=%s, id=%d",
                    code,
                    ph_id,
                )
                return match.group(0)  # Фолбек: возвращаем как есть, если тег сломан

            # Восстанавливаем в зависимости от кода
            if code == "L":  # Link
                href = (
                    ph.original_markup.get("href", "")
                    if isinstance(ph.original_markup, dict)
                    else ""
                )
                title_val = (
                    ph.original_markup.get("title")
                    if isinstance(ph.original_markup, dict)
                    else None
                )
                title = f' "{title_val}"' if title_val else ""
                result = f"[{inner_content}]({href}{title})"
                logger.debug("Restored link: href=%s", href)
                return result

            elif code == "B":  # Bold (strong)
                return f"**{inner_content}**"
            elif code == "I":  # Italic (em)
                return f"*{inner_content}*"
            elif code == "D":  # strikethrough (del/s)
                return f"~~{inner_content}~~"

            return inner_content

        # Запускаем рекурсивную замену для поддержки вложенных инлайнов
        old_text = ""
        iteration = 0
        while old_text != text:
            old_text = text
            text = self.PAIRED_REGEX.sub(replace_paired, text)
            iteration += 1

        if iteration > 1:
            logger.debug("Paired tag replacement iterations: %d", iteration)

        return text

    def _restore_atomic_tags(self, text: str, unit: TranslationUnit) -> str:
        """Восстанавливает атомарные теги (код, картинки, брейки, HTML)."""
        
        def replace_atomic(match):
            tag_mask = match.group(0)  # Полный плейсхолдер: __X_N__
            
            ph = self._atomic_ph_map.get(tag_mask)
            if not ph:
                logger.warning("Atomic placeholder not found in map: mask=%s", tag_mask)
                return tag_mask

            # Делегируем обработку специализированным методам по типу тега
            if ph.node_type == "code_inline":
                return self._restore_code_inline(ph)
            elif ph.node_type == "math_inline":
                return self._restore_math_inline(ph)
            elif ph.node_type in ("softbreak", "hardbreak"):
                return self._restore_break(ph)
            elif ph.node_type == "image":
                return self._restore_image(ph, unit)
            elif ph.node_type == "html_inline" or ph.node_type == "tasklist_item":
                return self._restore_html_inline(ph)

            return str(ph.original_markup)

        return self.ATOMIC_REGEX.sub(replace_atomic, text)

    def _restore_code_inline(self, ph: Placeholder) -> str:
        """Восстанавливает inline код."""
        markup = str(ph.original_markup)
        result = f"`{markup}`" if not markup.startswith("`") else markup
        logger.debug(" Restored inline code")
        return result

    def _restore_math_inline(self, ph: Placeholder) -> str:
        """Восстанавливает inline математику."""
        markup = str(ph.original_markup)
        result = f"${markup}$" if not markup.startswith("$") else markup
        logger.debug(" Restored inline math")
        return result

    def _restore_break(self, ph: Placeholder) -> str:
        """Восстанавливает перенос строки."""
        result = "\n" if ph.node_type == "softbreak" else "<br>"
        logger.debug(" Restored break: type=%s", ph.node_type)
        return result

    def _restore_image(self, ph: Placeholder, unit: TranslationUnit) -> str:
        """Восстанавливает изображение."""
        if not isinstance(ph.original_markup, dict):
            logger.warning("Image placeholder has non-dict original_markup")
            return str(ph.original_markup)

        src = ph.original_markup.get("src", "")
        title_val = ph.original_markup.get("title")
        title = f' "{title_val}"' if title_val else ""

        alt = ph.original_markup.get("alt", "") or unit.original_text or "image"
        result = f"![{alt}]({src}{title})"
        logger.debug(" Restored image: src=%s", src)
        return result

    def _restore_html_inline(self, ph: Placeholder) -> str:
        """Восстанавливает HTML inline элементы."""
        content = str(ph.original_markup)

        # Особая обработка для task-list checkbox
        if 'class="task-list-item-checkbox"' in content:
            if 'checked="checked"' in content or "checked" in content:
                logger.debug(" Restored checked task list item")
                return "[x]"
            else:
                logger.debug(" Restored unchecked task list item")
                return "[ ]"

        # Для других html_inline возвращаем оригинальное содержимое
        return content
