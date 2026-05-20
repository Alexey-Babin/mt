import json
from typing import Dict, TypedDict


class LanguageRecord(TypedDict):
    en: str
    ru: str
    native: str
    iso: str
    ord: int


def read_languages_db():
    with open("languages.json", "r") as json_file:
        languages: Dict[str, LanguageRecord] = json.load(json_file)
        return languages
