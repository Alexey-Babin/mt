import logging
import os

from engine import Translator
from fastapi import FastAPI
from pydantic import BaseModel

# Логирование
logger = logging.getLogger("uvicorn.error")
if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
app = FastAPI(title="NLLB Translation Server")

# Модель можно задать в переменной окружения
MODEL_NAME = os.environ.get("MT_MODEL", "nllb-200-distilled-600M")
MODELS_STORAGE = "../models" if __name__ == "__main__" else "/app/models"
MODEL_PATH = os.path.join(MODELS_STORAGE, MODEL_NAME)
logger.debug(f"Working with model {MODEL_NAME}")
logger.debug(f"{MODEL_PATH=}")

translator = Translator(path_to_model=MODEL_PATH)
if not translator.has_cuda:
    logger.warning("No CUDA device found")
logger.info(
    f"Initialized translator with model {MODEL_NAME} on device {translator.device}"
)


@app.get("/")
async def root():
    return "The server is up and running"


@app.get("/health")
def health():
    return {"status": "ok", "gpu": translator.has_cuda}


@app.get("/languages")
def get_languages():
    return {"codes": translator.get_supported_languages()}


class TranslationRequest(BaseModel):
    text: str
    src_lang: str
    target_lang: str


@app.post("/translate")
async def translate(req: TranslationRequest):
    result = translator.translate(req.text, req.src_lang, req.target_lang)
    return {"translated_text": result}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
