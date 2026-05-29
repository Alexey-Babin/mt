import os
from dataclasses import dataclass

TRUE_VALUES = ["true", "1", "t", "yes", "y"]


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

    executor_max_workers: int = int(
        os.environ.get(
            "MT_EXECUTOR_MAX_WORKERS",
            "2",
        )
    )

    debug_mode: bool = os.environ.get("DEBUG", "0").lower() in TRUE_VALUES


settings = MTConfig()
