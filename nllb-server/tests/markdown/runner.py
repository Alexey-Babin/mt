from mt_server.engine import Translator
from mt_server.translation_service import TranslationService


def run_translation(text: str) -> str:
    translator = Translator("/opt/mt/models/nllb-200-distilled-600M")
    service = TranslationService(translator)

    return service.translate(
        text=text,
        src_lang="eng_Latn",
        tgt_lang="rus_Cyrl",
    )
