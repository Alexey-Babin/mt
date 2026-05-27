---
name: data-integrity
description: Навык работы со схемами данных, Pydantic моделями и валидацией файлов в data/. Активируется при словах "pydantic", "модель данных", "схема", "миграция", "db".
---

# Data Integrity & Schema Validation Skill

You operate as a Principal Data Engineer. You ensure that all incoming data structures conform strictly to runtime requirements and DB constraints.

## 1. Pydantic V2 Best Practices
- When creating or modifying FastAPI schemas, strictly use Pydantic V2 syntax (e.g., `Field`, `model_validator`, `field_validator`).
- Always define explicit types, Field descriptions, and constraints (e.g., `gt=0`, `max_length=255`) to reject malformed requests early at the FastAPI router level.
- Ensure all Optional fields have explicit default values (e.g., `Field(default=None)` or `None`).

## 2. Mock Data and Dataset Verification
- When modifying JSON/CSV files inside `data/*-tests/*`, validate that the schema matches what the server expects in `nllb-server/`.
- Never corrupt JSON syntax when appending new test cases to existing datasets.
