"""Run llama.cpp's convert_hf_to_gguf.py on a Gemma 4 unified checkpoint.

transformers >= 5.20 drops `text_config.global_head_dim` from AutoConfig.to_dict(), which the
llama.cpp b9960 Gemma 4 converter requires. Read config.json directly instead; everything else
is the unmodified upstream converter.

    python ml/scripts/convert_gemma4_gguf.py ~/src/llama.cpp CHECKPOINT_DIR --outfile out.gguf
"""

import json
import runpy
import sys
from pathlib import Path

llama_cpp = Path(sys.argv.pop(1)).expanduser()
sys.path.insert(0, str(llama_cpp))
sys.path.insert(0, str(llama_cpp / "gguf-py"))

from conversion import base  # noqa: E402


def load_hparams(dir_model: Path, is_mistral_format: bool) -> dict:
    return json.loads((Path(dir_model) / "config.json").read_text())


base.ModelBase.load_hparams = staticmethod(load_hparams)
sys.argv[0] = str(llama_cpp / "convert_hf_to_gguf.py")
runpy.run_path(sys.argv[0], run_name="__main__")
