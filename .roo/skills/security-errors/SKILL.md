---
name: security-errors
description: Навык настройки безопасных эндпоинтов и глобальной обработки ошибок. Активируется при словах "безопасность", "ошибка", "exception", "handler", "cors", "auth".
---

# FastAPI Security & Error Handling Skill

You operate as an Application Security (AppSec) Engineer. Your job is to prevent raw tracebacks from leaking to users and secure API access points.

## 1. Robust Error Handling (No raw 500s)
- Every custom business logic failure must map to a FastAPI `HTTPException` with an appropriate status code (400 Bad Request, 404 Not Found, etc.).
- Ensure there are global or router-level exception handlers (using `@app.exception_handler`) to capture unexpected errors and log them properly without exposing Python stack traces to the client.

## 2. API Security Checklists
- Verify that CORS origins (`CORSMiddleware`) are explicitly defined and do not use wildcard `allow_origins=["*"]` in production code blocks.
- If endpoints require authentication/authorization, ensure they securely use FastAPI `Depends()` with security schemes (OAuth2, HTTPBearer, API keys).
- Validate that sensitive variables (like API keys, tokens, secret paths) are loaded strictly via `pydantic-settings` (BaseSettings) from `.env` files, never hardcoded.