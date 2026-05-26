# src/mt_server/markdown/translator.py

import logging
import re
from typing import Any, Dict, List

import html2text
import markdown
from bs4 import BeautifulSoup
from bs4.element import NavigableString

from .extractor import (
    IGNORE_TAGS,
    TRANSLATABLE_TAGS,
    MarkdownTranslationUnitExtractor,
)
from .placeholders import translate_html_content
from .units import MarkdownTranslationUnit

logger = logging.getLogger(__name__)


class MarkdownTranslator:
    """
    Основной класс перевода Markdown документов.

    Pipeline:
    1. Markdown -> HTML (используем библиотеку markdown)
    2. HTML -> Список блоков (tokens)
    3. Извлечение текста (Extractor)
    4. Перевод текста с сохранением HTML-структуры внутри блоков (placeholders)
    5. Сборка HTML -> Markdown (html2text)
    """

    def __init__(self, translator_engine):
        self.engine = translator_engine
        self.extractor = MarkdownTranslationUnitExtractor()

        # Настройка конвертеров
        self.md_converter = markdown.Markdown(
            extensions=["tables", "fenced_code", "toc", "pymdownx.tasklist"]
        )
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.body_width = 0  # Отключаем перенос строк

    def translate(self, markdown_text: str, src_lang: str, tgt_lang: str) -> str:
        if not markdown_text or not markdown_text.strip():
            return markdown_text

        logger.info(f"Starting Markdown translation: {src_lang} -> {tgt_lang}")

        try:
            # 1. Markdown -> HTML
            html_body = self._markdown_to_html(markdown_text)
            if not html_body.strip():
                logger.warning("Empty HTML generated from input.")
                return markdown_text

            # 2. Разбиение на логические блоки (токены)
            # Разбиваем по основным блочным тегам для удобства обработки
            tokens = self._split_html_to_tokens(html_body)

            # 3. Извлечение юнитов
            units = self.extractor.extract(tokens)
            if not units:
                logger.info("No translatable units found.")
                return markdown_text

            # 4. Перевод юнитов с сохранением внутренней структуры
            translated_units = self._translate_units(units, src_lang, tgt_lang)

            # 5. Сборка обратно в HTML
            final_html = self._rebuild_html(tokens, translated_units)

            # 6. HTML -> Markdown
            result_md = self._html_to_markdown(final_html)

            logger.info("Markdown translation completed successfully.")
            return result_md

        except Exception as e:
            logger.error(
                f"Critical error during markdown translation: {e}", exc_info=True
            )
            # Fallback: возвращаем оригинал, чтобы не ломать пайплайн полностью
            return markdown_text

    def _translate_units(
        self, units: List[MarkdownTranslationUnit], src: str, tgt: str
    ) -> List[MarkdownTranslationUnit]:
        """
        Переводит список юнитов.
        Ключевой момент: переводим не просто текст, а восстанавливаем HTML-контент.
        """
        for unit in units:
            original_html = unit.metadata.get("original_html", "")

            if not original_html:
                logger.warning(
                    f"Unit {unit.id} has no original HTML, skipping structure preservation."
                )
                continue

            # Функция перевода для одного куска текста
            def translate_fn(text_chunk: str) -> str:
                if not text_chunk.strip():
                    return text_chunk
                return self.engine.translate(text_chunk, src, tgt)

            # Магия здесь: translate_html_content пройдет по тегам внутри original_html
            # и заменит только текстовые узлы, вызывая translate_fn.
            translated_html = translate_html_content(original_html, translate_fn)

            # Обновляем юнит: теперь его "текст" - это уже готовый HTML блок
            unit.text = translated_html
            unit.metadata["is_html"] = True

        return units

    def _markdown_to_html(self, md: str) -> str:
        """Конвертирует MD в HTML body (без обертки html/head/body)."""
        try:
            # Сбрасываем состояние конвертера перед новым использованием
            self.md_converter.reset()
            return self.md_converter.convert(md)
        except Exception as e:
            logger.error(f"Markdown to HTML conversion failed: {e}")
            return ""

    def _split_html_to_tokens(self, html: str) -> List[Dict[str, Any]]:
        """
        Разбивает HTML строку на список блоков-токенов.
        Простая эвристика: разделение по блочным тегам.
        """
        tokens = []
        soup = BeautifulSoup(html, "html.parser")

        # Рекурсивный обход всех блочных элементов
        def traverse(node):
            if isinstance(node, NavigableString):
                return

            # Если это блочный элемент, который мы хотим переводить отдельно
            if node.name in TRANSLATABLE_TAGS:
                tokens.append(
                    {
                        "type": "Tag",
                        "tag": node.name,
                        "content": str(node),  # Сохраняем весь тег с содержимым
                    }
                )
                # Не идем глубже, чтобы не дублировать контент (если внутри p есть b, мы берем весь p)
                return

            # Если это теги, которые нужно сохранить без изменений (код и т.д.)
            if node.name in IGNORE_TAGS:
                tokens.append(
                    {
                        "type": "Tag",
                        "tag": node.name,
                        "content": str(node),  # Сохраняем весь тег с содержимым
                    }
                )
                return

            # Если это контейнер списка (ul/ol), обрабатываем его целиком для сохранения структуры
            if node.name in ["ul", "ol"]:
                tokens.append(
                    {
                        "type": "Tag",
                        "tag": node.name,
                        "content": str(node),  # Сохраняем весь список целиком
                    }
                )
                return

            # Если это li с вложенным списком, тоже сохраняем целиком
            if node.name == "li":
                has_nested_list = any(
                    child.name in ["ul", "ol"]
                    for child in node.children
                    if hasattr(child, "name")
                )
                if has_nested_list:
                    tokens.append(
                        {
                            "type": "Tag",
                            "tag": node.name,
                            "content": str(
                                node
                            ),  # Сохраняем весь li с вложенным списком
                        }
                    )
                    return
                # Если нет вложенного списка, идём внутрь
                for child in node.children:
                    traverse(child)
                return

            # Если это контейнер (div, section, body), идем внутрь
            if node.name in [
                "div",
                "section",
                "article",
                "body",
                "td",
                "th",
                "blockquote",
            ]:
                for child in node.children:
                    traverse(child)

        # Запускаем с корня (может быть несколько корневых элементов в фрагменте)
        for child in soup.children:
            traverse(child)

        return tokens

    def _rebuild_html(
        self,
        original_tokens: List[Dict],
        translated_units: List[MarkdownTranslationUnit],
    ) -> str:
        """
        Собирает финальный HTML из переведенных юнитов.
        Так как юниты содержат уже готовый HTML (с тегами), просто склеиваем их.
        """
        # Создаем мапу для быстрого доступа: token_index -> translated_html
        translation_map = {
            u.metadata["token_index"]: u.text
            for u in translated_units
            if u.metadata.get("is_html")
        }

        result_parts = []
        for idx, token in enumerate(original_tokens):
            if idx in translation_map:
                result_parts.append(translation_map[idx])
            else:
                # Если токен не переводился (например, был пропущен), оставляем оригинал
                result_parts.append(token.get("content", ""))

        return "\n".join(result_parts)

    def _html_to_markdown(self, html: str) -> str:
        """Конвертирует HTML обратно в Markdown."""
        if not html.strip():
            return ""
        try:
            # Создаём кастомный конвертер с поддержкой сохранения inline-тегов
            html_converter = html2text.HTML2Text()
            html_converter.ignore_links = False
            html_converter.ignore_images = False
            html_converter.body_width = 0  # Отключаем перенос строк
            html_converter.ul_item_mark = "-"

            # Callback для сохранения инлайн-тегов (span, font, mark, и т.д.)
            def preserve_inline_tags(h2t, tag, attrs, start):
                inline_tags_to_preserve = {
                    "span",
                    "font",
                    "mark",
                    "small",
                    "sub",
                    "sup",
                    "b",
                    "i",
                    "u",
                    "s",
                    "strike",
                }

                # Обработка чекбоксов из task list
                if tag == "input" and attrs.get("type") == "checkbox":
                    if start:
                        checked = (
                            "checked" in attrs or attrs.get("checked") == "checked"
                        )
                        h2t.o("[x] " if checked else "[ ] ")
                        return True  # Остановить стандартную обработку
                    return True  # Игнорируем закрывающий тег

                # Обработка инлайн-тегов
                if tag in inline_tags_to_preserve:
                    if start:
                        attr_str = ""
                        for k, v in attrs.items():
                            if v:
                                attr_str += f' {k}="{v}"'
                        h2t.o(f"<{tag}{attr_str}>")
                    else:
                        h2t.o(f"</{tag}>")
                    return True  # Остановить стандартную обработку
                return False  # Продолжить стандартную обработку

            setattr(html_converter, "tag_callback", preserve_inline_tags)

            # Сохраняем пробелы - иначе побьётся разметка
            protected_html = re.sub(r" (?=[^>]*<(?:/?[a-zA-Z1-6]+|!))", "\x01", html)

            # Сначала находим все <pre><code class="language-XXX">...</code></pre>
            # и заменяем их на плейсхолдеры, чтобы html2text не трогал их содержимое
            code_blocks = []

            def save_code_block(match):
                lang_class = match.group(1) or ""
                code_content = match.group(2)
                # Извлекаем язык из класса вида "language-python" -> "python"
                lang = lang_class.replace("language-", "") if lang_class else ""
                # Удаляем лишний начальный/конечный newline из контента
                code_content = code_content.strip("\n")
                # Сохраняем блок и возвращаем плейсхолдер
                code_blocks.append(f"```{lang}\n{code_content}\n```")
                return f"\x02CODEBLOCK{len(code_blocks) - 1}\x02"

            # Находим все <pre><code class="language-XXX">...</code></pre>
            protected_html = re.sub(
                r'<pre><code(?:\s+class="([^"]*)")?>(.*?)</code></pre>',
                save_code_block,
                protected_html,
                flags=re.DOTALL,
            )

            md = html_converter.handle(protected_html)

            # Восстанавливаем code блоки из плейсхолдеров
            for i, block in enumerate(code_blocks):
                md = md.replace(f"\x02CODEBLOCK{i}\x02", block)

            # Удаляем лишний пробел перед закрывающим тегом inline-элементов
            # html2text добавляет пробел после открывающего тега при использовании tag_callback
            md = re.sub(r"<(span|font|mark|small|sub|sup)([^>]*)>\s+", r"<\1\2>", md)

            # Нормализуем отступы списков:
            # html2text генерирует отступы с шагом 2 пробела, но начинает с 2 пробелов для первого уровня
            # Ожидаемый формат: 0 пробелов для уровня 1, 2 пробела для уровня 2, 4 пробела для уровня 3 и т.д.
            def normalize_list_indents(line):
                # Находим количество начальных пробелов
                match = re.match(r"^(\s*)([-*+]|\d+\.)\s", line)
                if match:
                    indent = match.group(1)
                    # Убираем 2 начальных пробела (которые html2text добавляет для первого уровня)
                    new_indent = max(0, len(indent) - 2)
                    return " " * new_indent + line.lstrip()
                return line

            md_lines = md.split("\n")
            normalized_lines = [normalize_list_indents(line) for line in md_lines]
            md = "\n".join(normalized_lines)

            return md.replace("\x01", " ")
        except Exception as e:
            logger.error(f"HTML to Markdown conversion failed: {e}")
            return html
