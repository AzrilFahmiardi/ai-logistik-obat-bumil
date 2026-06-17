import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

LLM_MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"

_model: AutoModelForCausalLM = None
_tokenizer: AutoTokenizer = None


def load():
    """Load Qwen3-4B-Instruct 4-bit NF4. Requires CUDA."""
    global _model, _tokenizer

    if not torch.cuda.is_available():
        raise RuntimeError(
            "Qwen3-4B-Instruct requires a CUDA-capable GPU. "
            "No GPU detected. Deploy this service on a machine with an NVIDIA GPU."
        )

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    _tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_ID)
    _model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_ID,
        quantization_config=quant_config,
        device_map="auto",
    )
    _model.eval()


def generate_reply(messages: list, max_new_tokens: int = 200) -> str:
    """Greedy generation for one chat exchange. Model must be loaded first."""
    if _model is None:
        raise RuntimeError("LLM not loaded. Call llm.load() at startup.")

    encoded = _tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(_model.device)

    with torch.no_grad():
        output = _model.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=_tokenizer.eos_token_id,
        )

    prompt_length = encoded["input_ids"].shape[1]
    return _tokenizer.decode(output[0][prompt_length:], skip_special_tokens=True)


def is_loaded() -> bool:
    return _model is not None
