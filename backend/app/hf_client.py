"""
hf_client.py

Qwen2.5-Coder-3B-Instruct client using HuggingFace pipeline API.
Used by Layer 3 detection and AST extraction.

pipeline() replaces the manual tokenizer + model.generate() + batch_decode()
workflow. HuggingFace handles all of that internally. We pass in a messages
list and get a response string back in one call.

pipeline("text-generation") is the correct task type for instruction-tuned
chat models. It applies the chat template, runs generation, and decodes the
output automatically.

Singleton pattern ensures the model loads once and stays in memory.
Lazy import means torch is only required when the model actually runs,
so unit tests work without GPU packages installed.

Install:
    pip install transformers torch accelerate

Usage:
    from hf_client import HFClient

    client   = HFClient()
    response = client.chat(messages, max_new_tokens=150)
"""

MODEL_NAME = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


class HFClient:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load(self):
        if self._loaded and hasattr(self, "pipe"):
            return

        import torch
        from transformers import pipeline, logging
        logging.set_verbosity_error()

        self._loaded = False

        print("Loading Qwen2.5-Coder-1.5B-Instruct via pipeline...")

        try:
            self.pipe = pipeline(
                "text-generation",
                model      = MODEL_NAME,
                dtype      = torch.float16,
                device_map = "auto",
            )
            self._loaded = True
            print(f"Pipeline ready on {self.pipe.device}")

        except Exception as e:
            raise RuntimeError(f"[HFClient] Failed to load model: {e}")

    def chat(
        self,
        messages:       list[dict],
        max_new_tokens: int   = 512,
        temperature:    float = 0.1,
    ) -> str:
        from transformers import GenerationConfig

        self._load()

        generation_config = GenerationConfig(
            max_new_tokens = max_new_tokens,
            temperature    = temperature,
            do_sample      = temperature > 0,
        )

        output = self.pipe(
            messages,
            generation_config = generation_config,
        )

        return output[0]["generated_text"][-1]["content"].strip()

    def is_available(self) -> bool:
        try:
            return True
        except ImportError:
            return False