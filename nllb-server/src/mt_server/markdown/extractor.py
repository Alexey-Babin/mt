# src/mt_server/markdown/extractor.py

import logging
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from .units import MarkdownTranslationUnit

logger = logging.getLogger(__name__)

# Теги, которые считаем "транслируемыми блоками"
TRANSLATABLE_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "td",
    "th",
    "blockquote",
    "figcaption",
}
# Теги, которые игнорируем (код, навигация, метаданные)
IGNORE_TAGS = {"pre", "code", "script", "style", "img", "br", "hr"}


class MarkdownTranslationUnitExtractor:
    """
    Извлекает единицы перевода из HTML-представления Markdown.
    Работает на уровне блочных элементов.
    """

    def extract(self, tokens: List[Dict[str, Any]]) -> List[MarkdownTranslationUnit]:
        """
        Принимает список токенов (HTML-блоки), возвращает список юнитов.

        Ожидается, что каждый токен имеет структуру:
        {"type": "Tag", "tag": "p", "content": "<p>Text <b>bold</b></p>"}
        """
        units = []

        for idx, token in enumerate(tokens):
            tag_name = token.get("tag", "").lower()
            content = token.get("content", "")

            if not content or not tag_name:
                continue

            if tag_name in IGNORE_TAGS:
                logger.debug(f"Skipping non-translatable block: {tag_name}")
                continue

            if tag_name not in TRANSLATABLE_TAGS:
                # Если тег неизвестен, пробуем извлечь текст, но с осторожностью
                logger.debug(f"Unknown tag {tag_name}, attempting extraction.")

            try:
                # Парсим контент токена чтобы получить чистый текст
                soup = BeautifulSoup(content, "html.parser")
                text_content = soup.get_text(separator=" ", strip=True)

                if not text_content:
                    continue

                unit = MarkdownTranslationUnit(
                    id=f"unit_{idx}_{tag_name}",
                    text=text_content,
                    metadata={
                        "token_index": idx,
                        "tag": tag_name,
                        "original_html": content,
                    },
                )
                units.append(unit)

            except Exception as e:
                logger.error(
                    f"Failed to extract text from token {idx} ({tag_name}): {e}"
                )
                continue

        logger.info(
            f"Extracted {len(units)} translation units from {len(tokens)} tokens."
        )
        return units
