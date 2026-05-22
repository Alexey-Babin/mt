# Markdown Regression Test Suite

## Назначение

Regression tests для markdown translation pipeline.

Тесты проверяют:

- markdown structure preservation
- AST consistency
- links preservation
- code block preservation
- inline code preservation
- tables validity
- nested formatting correctness
- markdown semantics preservation

## Структура тест-кейса

Каждый каталог содержит:

- input.md
- expected.md
- rules.json

## Важно

expected.md НЕ используется для strict equality comparison.

Основная проверка:
- AST invariants
- markdown validity
- preservation rules
