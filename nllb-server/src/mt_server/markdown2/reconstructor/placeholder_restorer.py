"""Модуль восстановления плейсхолдеров в Markdown-разметке.

Отвечает за:
- Нормализацию текста (очистка пробелов вокруг масок)
- Восстановление парных тегов (ссылки, strong, em, del)
- Восстановление атомарных тегов (code_inline, math_inline, image, breaks)
"""

import logging
from typing import Dict, List, Tuple

import regex as re

from ..placeholder import Placeholder
from ..translation_unit import TranslationUnit

logger = logging.getLogger("uvicorn.error")


class PlaceholderRestorer:
    """Восстанавливает плейсхолдеры обратно в Markdown-разметку."""

    # Префиксы для парных транслируемых тегов
    PAIRED_TRANSLATE_PREFIXES = {"s", "e", "del", "lnk"}

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
            clean_mask = ph.tag_mask.strip()

            # Извлекаем числовой ID из маски (например, из "{lnk_1}" вытаскиваем 1)
            if match := re.search(r"\d+", clean_mask):
                ph_id = int(match.group())
                prefix = clean_mask[1:-1].split("_")[0]

                if ph.is_closing:
                    # Закрывающие плейсхолдеры не добавляем в карты для поиска открывающих
                    continue

                # Для парных тегов без суффиксов (strong, link, em, s)
                if prefix in self.PAIRED_TRANSLATE_PREFIXES:
                    self._open_ph_map[(prefix, ph_id)] = ph
                # Для атомарных тегов (code_inline, math_inline, etc.)
                elif ph.node_type.endswith("_open") or not any(
                    ph.node_type.endswith(suffix) for suffix in ["_open", "_close"]
                ):
                    self._atomic_ph_map[clean_mask] = ph

        logger.debug(
            "Placeholder maps built: open_tags=%d, atomic_tags=%d",
            len(self._open_ph_map),
            len(self._atomic_ph_map),
        )

    def normalize_text(self, text: str, placeholders: List[Placeholder]) -> str:
        """Нормализует текст, убирая фантомные пробелы вокруг масок.

        Приводит маски к стандартному виду "{tag_id}".
        Не добавляет пробел после закрывающего тега, если следующий символ - пунктуация.
        """
        normalized_text = text
        for ph in placeholders:
            clean_mask = ph.tag_mask.strip()
            inner_mask = clean_mask[1:-1]
            
            if ph.is_closing:
                # Для закрывающих тегов: пробел перед тегом
                # После тега: пробел НЕ добавляем, если следующий символ - пунктуация
                # Сначала обрабатываем случай с пунктуацией
                normalized_text = re.sub(
                    r"\s*\{\s*" + re.escape(inner_mask) + r"\s*\}\s*([.,!?;:])",
                    f" {clean_mask}\\1",
                    normalized_text,
                )
                # Затем обрабатываем остальные случаи (если ещё не обработано)
                normalized_text = re.sub(
                    r"\s*\{\s*" + re.escape(inner_mask) + r"\s*\}(?!\s*[.,!?;:])(\s*)",
                    lambda m: f" {clean_mask} " if m.group(1) or not m.end() == len(normalized_text) else f" {clean_mask}",
                    normalized_text,
                )
            else:
                # Для открывающих тегов: пробелы с обеих сторон
                normalized_text = re.sub(
                    r"\s*\{\s*" + re.escape(inner_mask) + r"\s*\}\s*",
                    f" {clean_mask} ",
                    normalized_text,
                )
        return normalized_text

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
        # Регулярка находит: {префикс_ID} текст {/префикс_ID}
        paired_regex = re.compile(
            r"\{\s*([a-zA-Z]+)_(\d+)\s*\}(.*?)\{\s*/\1_\2\s*\}", re.DOTALL
        )

        def replace_paired(match):
            prefix = match.group(1)
            ph_id = int(match.group(2))
            inner_content = match.group(3).strip()

            ph = self._open_ph_map.get((prefix, ph_id))
            if not ph:
                logger.warning(
                    "Paired placeholder not found in map: prefix=%s, id=%d",
                    prefix,
                    ph_id,
                )
                return match.group(0)  # Фолбек: возвращаем как есть, если тег сломан

            if prefix == "lnk":
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

            elif prefix == "s":
                return f"**{inner_content}**"
            elif prefix == "e":
                return f"*{inner_content}*"
            elif prefix == "del":
                return f"~~{inner_content}~~"

            return inner_content

        # Запускаем рекурсивную замену для поддержки вложенных инлайнов
        old_text = ""
        iteration = 0
        while old_text != text:
            old_text = text
            text = paired_regex.sub(replace_paired, text)
            iteration += 1

        if iteration > 1:
            logger.debug("Paired tag replacement iterations: %d", iteration)

        return text

    def _restore_atomic_tags(self, text: str, unit: TranslationUnit) -> str:
        """Восстанавливает атомарные теги (код, картинки, брейки, HTML)."""
        atomic_regex = re.compile(r"\{\s*([a-zA-Z0-9_/]+)\s*\}")

        return atomic_regex.sub(
            lambda match: self._replace_atomic_tag(match, unit), text
        )

    def _replace_atomic_tag(self, match, unit: TranslationUnit) -> str:
        """Заменяет один атомарный тег."""
        full_mask = f"{{{match.group(1)}}}"
        ph = self._atomic_ph_map.get(full_mask)

        if not ph:
            logger.warning("Atomic placeholder not found in map: mask=%s", full_mask)
            return full_mask

        # Делегируем обработку специализированным методам по типу тега
        if ph.node_type == "code_inline":
            return self._restore_code_inline(ph)
        elif ph.node_type == "math_inline":
            return self._restore_math_inline(ph)
        elif ph.node_type in ("softbreak", "hardbreak"):
            return self._restore_break(ph)
        elif ph.node_type == "image":
            return self._restore_image(ph, unit)
        elif ph.node_type == "html_inline" or (ph.tag_mask.strip().startswith("{chk_")):
            return self._restore_html_inline(ph)

        return str(ph.original_markup)

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
