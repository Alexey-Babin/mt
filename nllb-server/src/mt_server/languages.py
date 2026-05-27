import json
import logging
import pathlib
from typing import Dict, TypedDict

LANGUAGES_DB_FILE = pathlib.Path(__file__).parent.parent.parent / "languages.json"

logger = logging.getLogger("uvicorn.error")


class LanguageRecord(TypedDict):
    en: str
    ru: str
    native: str
    iso: str
    iso2: str
    ord: int


def read_languages_db():
    with open(LANGUAGES_DB_FILE, "r") as json_file:
        languages: Dict[str, LanguageRecord] = json.load(json_file)
        logger.debug(f"Read {len(languages)} languages from json file")
        return languages


languages_db = read_languages_db()
