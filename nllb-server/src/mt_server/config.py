import os
from dataclasses import dataclass


@dataclass(slots=True)
class MTConfig:
    model_name: str = os.environ.get(
        "MT_MODEL",
        "nllb-200-distilled-600M",
    )

    model_storage: str = os.environ.get(
        "MT_MODELS_STORAGE",
        "/opt/mt/models",
    )

    max_input_tokens: int = int(
        os.environ.get(
            "MT_MAX_INPUT_TOKENS",
            "384",
        )
    )

    tokenizer_max_length: int = int(
        os.environ.get(
            "MT_TOKENIZER_MAX_LENGTH",
            "512",
        )
    )

    max_new_tokens: int = int(
        os.environ.get(
            "MT_MAX_NEW_TOKENS",
            "256",
        )
    )

    model_compile: bool = (
        os.environ.get(
            "MT_MODEL_COMPILE",
            "0",
        )
        == "1"
    )


settings = MTConfig()
