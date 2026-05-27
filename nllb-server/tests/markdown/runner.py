import os

from mt_server.translation_service import TranslationService

# Check if we should use mock translator
USE_MOCK = os.environ.get("USE_MOCK_TRANSLATOR", "false").lower() == "true"

if USE_MOCK:
    from tests.mock_translator import MockTranslationEngine as TranslationEngine
else:
    from mt_server.engine import NllbTranslationEngine as TranslationEngine

print(f"{USE_MOCK=}")


def run_translation(text: str) -> str:

    if USE_MOCK:
        translator = TranslationEngine("")
    else:
        translator = TranslationEngine("/opt/mt/models/nllb-200-distilled-600M")
    service = TranslationService(translator)

    return service.translate(
        text=text,
        src_lang="eng_Latn",
        tgt_lang="rus_Cyrl",
    )
