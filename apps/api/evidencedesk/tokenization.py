from functools import lru_cache
from pathlib import Path

from tokenizers import Tokenizer


@lru_cache
def tokenizer() -> Tokenizer:
    return Tokenizer.from_file(str(Path(__file__).parent / "assets" / "tokenizer.json"))


def token_count(text: str) -> int:
    return len(tokenizer().encode(text).ids)


def check_embedding_input(text: str) -> None:
    if token_count(text) > 512:
        raise ValueError("Embedding input exceeds the model's 512-token limit")
