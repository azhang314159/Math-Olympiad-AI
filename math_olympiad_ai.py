# -*- coding: utf-8 -*-
"""Math Olympiad AI

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1DPhD7ULOfQmAfr8eKRwg9Omhj6KQU-Fx

### Setup
Fine-tuning Llama-3 8B to solve problems from mathematical olympiads (AMC 10, AMC 12, AIME, etc.)
"""

!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps xformers "trl<0.9.0" peft accelerate bitsandbytes

from unsloth import FastLanguageModel
import torch

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-bnb-4bit",
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True
)

model = FastLanguageModel.get_peft_model(
    model,
    r = 16,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
    use_rslora = False,
    loftq_config = None,
)

"""### Dataset
We use the MATH dataset from [hendryks](https://huggingface.co/datasets/hendrycks/competition_math). This dataset consists of problems from mathematics competitions, including the AMC 10, AMC 12, AIME, and more. Each problem in MATH has a full step-by-step solution, which can be used to teach models to generate answer derivations and explanations.
"""

math_prompt = """Write a solution to the following math problem.

### Problem:
{}

### Solution:
{}"""

EOS_TOKEN = tokenizer.eos_token
def formatter(examples):
    problems  = examples["problem"]
    solutions = examples["solution"]
    texts = []
    for problem, solution in zip(problems, solutions):
        text = math_prompt.format(problem, solution) + EOS_TOKEN
        texts.append(text)
    return { "text" : texts, }
pass

from datasets import load_dataset
dataset = load_dataset("hendrycks/competition_math", split = "train")
dataset = dataset.map(formatter, batched = True,)

"""### Model Training"""

from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = 2048,
    dataset_num_proc = 2,
    packing = False,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 60,
        learning_rate = 2e-4,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
    ),
)

trainer_stats = trainer.train()

"""### Inference
Test the model with a competition math problem.
"""

FastLanguageModel.for_inference(model)
inputs = tokenizer(
[
    math_prompt.format(
        "If $x + \frac{1}{x} = 3$, determine the value of $x^2 + \frac{1}{x^2}$.",
        "",
    )
], return_tensors = "pt").to("cuda")

from transformers import TextStreamer
text_streamer = TextStreamer(tokenizer)
_ = model.generate(**inputs, streamer = text_streamer, max_new_tokens = 128)