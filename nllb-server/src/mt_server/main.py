import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .config import settings
from .engine import Translator
from .translation_service import TextFormat, TranslationService

# Логирование
logger = logging.getLogger("uvicorn.error")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
DEBUG = os.environ.get("DEBUG", "0") == "1"
if DEBUG:
    logger.setLevel(logging.DEBUG)

logger.debug(f"Working with model {settings.model_name}")
logger.debug(f"{settings.model_storage=}")


class LanguageLevels(StrEnum):
    MEMBERS_ONLY = "members_only"
    FORMER_MEMBERS = "former_members"
    NOT_MEMBER = "all"


# -------------------------------------------------------------
# Глобальные зависимости
translator_engine: Optional[Translator] = None
translation_service: Optional[TranslationService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация и shutdown приложения."""
    global translator_engine, translation_service

    logger.info("Loading NLLB model...")
    try:
        # Инициализация тяжелого движка
        translator_engine = Translator(model_name=settings.model_name)
        # Инициализация сервиса (обертка над движком)
        translation_service = TranslationService(translator_engine)
        if not translator_engine.has_cuda:
            logger.warning("No CUDA device found")
        logger.info(
            f"Initialized translator with model {settings.model_name} on device {translator_engine.device}"
        )
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)
    # ------------------------------------------------------------------
    yield
    # ---------------------SHUTDOWN-------------------------------------
    logger.info("Shutting down...")
    translator_engine = None
    translation_service = None


app = FastAPI(title="NLLB Translation Server", lifespan=lifespan)


class TranslateRequest(BaseModel):
    text: str
    src_lang: str
    target_lang: str
    format: TextFormat = TextFormat.AUTO


class TranslateResponse(BaseModel):
    translated_text: str
    source_lang: str
    target_lang: str


@app.post("/translate", response_model=TranslateResponse)
async def translate_endpoint(request: TranslateRequest):
    if not request.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # # Валидация языков
    # try:
    #     validate_language_pair(request.source_lang, request.target_lang)
    # except ValueError as e:
    #     raise HTTPException(status_code=400, detail=str(e))

    if translation_service is None:
        raise HTTPException(status_code=503, detail="Translation service not ready")

    try:
        # Выносим блокирующий вызов в отдельный поток через asyncio.to_thread()
        # Это предотвращает блокировку event loop при тяжелых операциях перевода
        result = await asyncio.to_thread(
            translation_service.translate,
            text=request.text,
            src_lang=request.src_lang,
            tgt_lang=request.target_lang,
            format=request.format,
        )

        return TranslateResponse(
            translated_text=result,
            source_lang=request.src_lang,
            target_lang=request.target_lang,
        )
    except Exception as e:
        logger.error(f"Endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal translation error")


@app.get("/health")
async def health_check():

    if translator_engine and translation_service:
        return {
            "status": "ready",
            "model": translator_engine.model_name,
            "gpu": translator_engine.has_cuda,
            "device": translator_engine.device,
        }
    else:
        return {"status": "loading"}


@app.get("/languages")
def get_languages(
    language_level: LanguageLevels = Query(
        LanguageLevels.MEMBERS_ONLY, description="Страны-члены, бывшие члены и все"
    ),
):

    if translator_engine:
        lang_list = {
            lang[0]: lang[1]
            for lang in translator_engine.languages.items()
            if (
                (
                    language_level == "members_only"
                    and lang[1]
                    and lang[1].get("ord") < 10
                )
                or (
                    language_level == "former_members"
                    and lang[1]
                    and lang[1].get("ord") < 100
                )
                or (language_level == "all")
            )
        }
        return lang_list
    else:
        return {}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG)
