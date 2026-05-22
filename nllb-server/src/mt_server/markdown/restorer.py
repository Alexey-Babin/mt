# nllb-server/src/mt_server/markdown/restorer.py
from __future__ import annotations

import logging

from markdown_it.token import Token

from mt_server.markdown.units import TranslationUnit

logger = logging.getLogger("uvicorn.error")


class MarkdownRestorer:
    """
    Восстанавливает Markdown-текст после перевода.

    Обходит список токенов markdown-it и сериализует их обратно
    в Markdown (не в HTML), подставляя переведённые тексты.
    """

    def restore(
        self,
        tokens: list[Token],
        units: list[TranslationUnit],
    ) -> str:
        # Строим словарь: индекс inline-токена → переведённый текст
        translated: dict[int, str] = {
            unit.inline_token_index: unit.text for unit in units
        }

        lines: list[str] = []
        # Стек контекстов: "blockquote", "bullet_list", "ordered_list"
        context_stack: list[str] = []
        # Текущий маркер элемента списка (- или 1.)
        list_item_marker: str = ""
        # Счётчик для нумерованных списков
        ordered_counters: list[int] = []

        i = 0
        while i < len(tokens):
            token = tokens[i]

            match token.type:
                # ── blockquote ───────────────────────────────────────────────
                case "blockquote_open":
                    context_stack.append("blockquote")

                case "blockquote_close":
                    if context_stack and context_stack[-1] == "blockquote":
                        context_stack.pop()
                    # Пустой blockquote (> без содержимого) — выводим пустую строку с префиксом
                    # Проверяем: следующий токен — тоже blockquote или конец
                    # Пустые blockquote_open/close без inline внутри уже обработаны
                    # через отсутствие inline-токенов — добавим пустую строку
                    # только если между open и close не было inline
                    if not lines or lines[-1] != "":
                        pass  # ничего не добавляем — пустые блоки обработаем ниже

                # ── bullet list ──────────────────────────────────────────────
                case "bullet_list_open":
                    context_stack.append("bullet_list")

                case "bullet_list_close":
                    if context_stack and context_stack[-1] == "bullet_list":
                        context_stack.pop()

                # ── ordered list ─────────────────────────────────────────────
                case "ordered_list_open":
                    context_stack.append("ordered_list")
                    ordered_counters.append(int(token.attrGet("start") or 1))

                case "ordered_list_close":
                    if context_stack and context_stack[-1] == "ordered_list":
                        context_stack.pop()
                    if ordered_counters:
                        ordered_counters.pop()

                # ── list item ────────────────────────────────────────────────
                case "list_item_open":
                    if context_stack and context_stack[-1] == "ordered_list":
                        n = ordered_counters[-1] if ordered_counters else 1
                        list_item_marker = f"{n}."
                        if ordered_counters:
                            ordered_counters[-1] += 1
                    else:
                        # Берём маркер из markup токена (-, *, +)
                        list_item_marker = token.markup or "-"

                case "list_item_close":
                    list_item_marker = ""

                # ── heading ──────────────────────────────────────────────────
                case "heading_open":
                    # Уровень: h1→#, h2→##, …
                    level = int(token.tag[1]) if token.tag else 1
                    # Следующий токен — inline
                    if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                        inline_ix = i + 1
                        text = translated.get(inline_ix, tokens[inline_ix].content)
                        prefix = _build_prefix(context_stack, list_item_marker)
                        lines.append(f"{prefix}{'#' * level} {text}")
                        i += 2  # пропускаем inline + heading_close
                        continue

                # ── paragraph ────────────────────────────────────────────────
                case "paragraph_open":
                    if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                        inline_ix = i + 1
                        text = translated.get(inline_ix, tokens[inline_ix].content)
                        prefix = _build_prefix(context_stack, list_item_marker)
                        # Для элемента списка маркер ставим один раз
                        lines.append(f"{prefix}{text}")
                        i += 2  # пропускаем inline + paragraph_close
                        continue

                # ── fence (code block) ───────────────────────────────────────
                case "fence":
                    info = token.info.strip() if token.info else ""
                    prefix = _build_prefix(context_stack, list_item_marker)
                    fence_marker = token.markup or "```"
                    lines.append(f"{prefix}{fence_marker}{info}")
                    # Содержимое блока кода — не переводим
                    for code_line in token.content.splitlines():
                        lines.append(f"{prefix}{code_line}")
                    lines.append(f"{prefix}{fence_marker}")

                # ── code block (indented) ────────────────────────────────────
                case "code_block":
                    prefix = _build_prefix(context_stack, list_item_marker)
                    for code_line in token.content.splitlines():
                        lines.append(f"{prefix}    {code_line}")

                # ── hr ───────────────────────────────────────────────────────
                case "hr":
                    prefix = _build_prefix(context_stack, list_item_marker)
                    lines.append(f"{prefix}---")

                # ── html_block ───────────────────────────────────────────────
                case "html_block":
                    lines.append(token.content.rstrip())

                # Всё остальное — игнорируем (inline обрабатывается выше)
                case _:
                    pass

            i += 1

        return _join_lines(lines)


# ── helpers ──────────────────────────────────────────────────────────────────


def _build_prefix(context_stack: list[str], list_item_marker: str) -> str:
    """
    Строит префикс строки на основе текущего стека контекстов.

    Каждый blockquote добавляет «> ».
    Элемент списка добавляет маркер («- » или «1. »).
    """
    parts: list[str] = []
    in_list = False

    for ctx in context_stack:
        if ctx == "blockquote":
            parts.append("> ")
        elif ctx in ("bullet_list", "ordered_list"):
            in_list = True

    if in_list and list_item_marker:
        parts.append(f"{list_item_marker} ")

    return "".join(parts)


def _join_lines(lines: list[str]) -> str:
    """
    Объединяет строки, разделяя смысловые блоки пустой строкой.

    Смежные строки с одинаковым «уровнем» (blockquote-глубиной)
    разделяются пустой строкой, чтобы Markdown оставался валидным.
    """
    if not lines:
        return ""

    result: list[str] = []
    for ix, line in enumerate(lines):
        result.append(line)
        # Добавляем пустую строку между блоками, кроме последнего
        if ix < len(lines) - 1:
            result.append("")

    # Финальный перевод строки
    return "\n".join(result) + "\n"
