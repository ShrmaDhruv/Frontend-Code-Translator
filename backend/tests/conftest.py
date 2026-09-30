import os

# Tests must never send traces to LangSmith, even when the root .env enables tracing
# (load_dotenv does not override variables that are already set).
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("OLLAMA_WARMUP", "0")
