"""Reference CUDA recipe with Unsloth (Colab, Kaggle, or any NVIDIA GPU with >=16 GB).

This repository trains on Apple Silicon with `evidencedesk_ml.train_mlx`, because the Unsloth
Python library does not train on Mac yet. This script keeps the same data, prompt rendering,
and hyperparameters so the run can move to a CUDA machine unchanged:

    pip install unsloth
    python ml/train_unsloth.py --data ml/data/sft --out ml/artifacts/unsloth-lora

It is not executed in CI.
"""

import argparse
import json
from pathlib import Path

END_OF_TURN = "<turn|>"


def render(tokenizer, path: Path) -> list[dict[str, str]]:
    """Render prompt and completion exactly like the serving path (see train_mlx.py)."""
    rows = []
    for line in path.read_text().splitlines():
        messages = json.loads(line)["messages"]
        prompt = tokenizer.apply_chat_template(
            messages[:-1], add_generation_prompt=True, tokenize=False
        )
        rows.append({"text": prompt + messages[-1]["content"] + END_OF_TURN})
    return rows


def main() -> None:
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import train_on_responses_only

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="unsloth/gemma-4-12b-it")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seq-length", type=int, default=3072)
    args = parser.parse_args()

    model, tokenizer = FastLanguageModel.from_pretrained(
        args.base, max_seq_length=args.max_seq_length, load_in_4bit=True
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
        ],
        use_gradient_checkpointing="unsloth",
        random_state=7,
    )
    train = Dataset.from_list(render(tokenizer, args.data / "train.jsonl"))
    valid = Dataset.from_list(render(tokenizer, args.data / "valid.jsonl"))
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train,
        eval_dataset=valid,
        args=SFTConfig(
            output_dir=str(args.out),
            dataset_text_field="text",
            max_seq_length=args.max_seq_length,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            num_train_epochs=1,
            learning_rate=1e-4,
            lr_scheduler_type="cosine",
            warmup_steps=15,
            weight_decay=0.0,
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=50,
            optim="adamw_8bit",
            seed=7,
            report_to="none",
        ),
    )
    # Loss on the answer only: everything up to the empty thought channel is the prompt.
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|turn>user\n",
        response_part="<|turn>model\n<|channel>thought\n<channel|>",
    )
    trainer.train()
    model.save_pretrained(str(args.out))
    tokenizer.save_pretrained(str(args.out))
    model.save_pretrained_gguf(str(args.out / "gguf"), tokenizer, quantization_method="q4_k_m")


if __name__ == "__main__":
    main()
