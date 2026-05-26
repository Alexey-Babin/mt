import os

from mt_server.translation_service import TranslationService

# Check if we should use mock translator
USE_MOCK = os.environ.get("USE_MOCK_TRANSLATOR", "false").lower() == "true"

if USE_MOCK:
    from tests.mock_translator import MockTranslator as Translator
else:
    from mt_server.engine import Translator


def run_translation(text: str) -> str:
    if USE_MOCK:
        translator = Translator("")
    else:
        translator = Translator("/opt/mt/models/nllb-200-distilled-600M")
    service = TranslationService(translator)

    return service.translate(
        text=text,
        src_lang="eng_Latn",
        tgt_lang="rus_Cyrl",
    )
