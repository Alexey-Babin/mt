# src/mt_server/markdown/translator.py

import logging
from typing import Any, Dict, List

import html2text
import markdown
from bs4 import BeautifulSoup
from bs4.element import NavigableString

from .extractor import TRANSLATABLE_TAGS, MarkdownTranslationUnitExtractor
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
            extensions=["tables", "fenced_code", "toc"]
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

            # Если это контейнер (div, section, body), идем внутрь
            if node.name in [
                "div",
                "section",
                "article",
                "body",
                "td",
                "th",
                "li",
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
            return self.html_converter.handle(html)
        except Exception as e:
            logger.error(f"HTML to Markdown conversion failed: {e}")
            return html
