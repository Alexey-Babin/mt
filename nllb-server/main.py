import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from enum import StrEnum

from config import config
from engine import Translator
from fastapi import FastAPI, Query
from pydantic import BaseModel

# Модель можно задать в переменной окружения
MODEL_PATH = os.path.join(config.model_storage, config.model_name)

# Логирование
logger = logging.getLogger("uvicorn.error")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
DEBUG = os.environ.get("DEBUG", "0") == "1"
if DEBUG:
    logger.setLevel(logging.DEBUG)

logger.debug(f"Working with model {config.model_name}")
logger.debug(f"{MODEL_PATH=}")


class TranslationRequest(BaseModel):
    text: str
    src_lang: str
    target_lang: str


class LanguageLevels(StrEnum):
    MEMBERS_ONLY = "members_only"
    FORMER_MEMBERS = "former_members"
    NOT_MEMBER = "all"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # ── Startup ─────────────────────────────────────
    app.state.translator = Translator(path_to_model=MODEL_PATH)

    if not app.state.translator.has_cuda:
        logger.warning("No CUDA device found")
    logger.info(
        f"Initialized translator with model {config.model_name} "
        f"on device {app.state.translator.device}"
    )

    yield  # ── Application runs here ────────────────

    # ── Shutdown ────────────────────────────────────
    tr = app.state.translator
    del tr.model
    del tr.tokenizer

    if tr.has_cuda:
        import torch

        torch.cuda.empty_cache()
    logger.info("Translator released")


def create_app():
    app = FastAPI(title="NLLB Translation Server", lifespan=lifespan)

    @app.get("/")
    async def root():
        return "The server is up and running"

    @app.get("/health")
    def health():
        tr = app.state.translator
        return {
            "status": "ok",
            "gpu": tr.has_cuda,
            "device": tr.device,
            "model": tr.model_name,
        }

    @app.get("/languages")
    def get_languages(
        language_level: LanguageLevels = Query(
            LanguageLevels.MEMBERS_ONLY, description="Страны-члены, бывшие члены и все"
        ),
    ):
        # 1. Filter by membership level (skip codes without metadata)
        filtered_langs = {
            code: meta
            for code, meta in app.state.translator.languages.items()
            if meta is not None
            and (
                (language_level == "members_only" and meta.get("ord", 999) < 10)
                or (language_level == "former_members" and meta.get("ord", 999) < 100)
                or (language_level == "all")
            )
        }

        # 2. Sort by country ordinal + Russian name
        return dict(
            sorted(
                filtered_langs.items(),
                key=lambda item: (
                    str(item[1].get("ord", "1000")) + "_" + item[1].get("ru")
                ),
            )
        )

    @app.post("/translate")
    async def translate(req: TranslationRequest):
        result = app.state.translator.translate(req.text, req.src_lang, req.target_lang)
        return {"translated_text": result}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG)
