import logging
import os
from enum import StrEnum

from engine import Translator
from fastapi import FastAPI, Query
from languages import read_languages_db
from pydantic import BaseModel

# Модель можно задать в переменной окружения
MODEL_NAME = os.environ.get("MT_MODEL", "nllb-200-distilled-600M")
MODELS_STORAGE = os.environ.get("MT_MODELS_STORAGE", "/apt/models")
MODEL_PATH = os.path.join(MODELS_STORAGE, MODEL_NAME)

# Логирование
logger = logging.getLogger("uvicorn.error")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
DEBUG = os.environ.get("DEBUG", "0") == "1"
if DEBUG:
    logger.setLevel(logging.DEBUG)

logger.debug(f"Working with model {MODEL_NAME}")
logger.debug(f"{MODEL_PATH=}")


class TranslationRequest(BaseModel):
    text: str
    src_lang: str
    target_lang: str


class LanguageLevels(StrEnum):
    MEMBERS_ONLY = "members_only"
    FORMER_MEMBERS = "former_members"
    NOT_MEMBER = "all"


def create_app():
    app = FastAPI(title="NLLB Translation Server")

    @app.on_event("startup")
    async def startup():
        tr = app.state.translator = Translator(path_to_model=MODEL_PATH)

        # Получаем список возможных языков (сразу из модели)
        model_lang_codes = tr.get_supported_languages()
        languages = read_languages_db()
        app.state.languages = dict(
            sorted(
                [
                    (lang_code, languages.get(lang_code))
                    for lang_code in model_lang_codes
                ],
                key=lambda lang: (
                    str(lang[1].get("ord", "1000")) + "_" + lang[1].get("ru")
                    if lang[1] is not None
                    else "9999999"
                ),
            )
        )

        if not tr.has_cuda:
            logger.warning("No CUDA device found")
        logger.info(
            f"Initialized translator with model {MODEL_NAME} on device {tr.device}"
        )

    @app.on_event("shutdown")
    async def shutdown():
        tr = app.state.translator
        del tr.model
        del tr.tokenizer

        if tr.has_cuda:
            import torch

            torch.cuda.empty_cache()
        logger.info("Translator released")

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

        lang_list = {
            lang[0]: lang[1]
            for lang in app.state.languages.items()
            if (
                (language_level == "members_only" and lang[1].get("ord") < 10)
                or (language_level == "former_members" and lang[1].get("ord") < 100)
                or (language_level == "all")
            )
        }

        return lang_list

    @app.post("/translate")
    async def translate(req: TranslationRequest):
        result = app.state.translator.translate(req.text, req.src_lang, req.target_lang)
        return {"translated_text": result}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG)
