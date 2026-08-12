"""Configuration loaded exclusively from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RUNTIME_DIR = PROJECT_ROOT / "runtime"


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    runtime_dir: Path = RUNTIME_DIR
    checkpoint_path: Path = RUNTIME_DIR / "checkpoints.db"
    operations_path: Path = RUNTIME_DIR / "operations.db"
    drafts_dir: Path = RUNTIME_DIR / "drafts"
    model_name: str = "llama-3.3-70b-versatile"
    embedding_backend: str = "huggingface"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    simulate_it_failure: bool = False

    @classmethod
    def from_env(cls, *, require_live_key: bool = False) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")
        if require_live_key and not os.getenv("GROQ_API_KEY"):
            raise RuntimeError(
                "GROQ_API_KEY is missing. Copy .env.example to .env and add the key, "
                "or use Colab Secrets. Never paste a key into source code."
            )

        settings = cls(
            model_name=os.getenv("ONBOARDAI_MODEL", "llama-3.3-70b-versatile"),
            embedding_backend=os.getenv("ONBOARDAI_EMBEDDINGS", "huggingface").lower(),
            embedding_model=os.getenv(
                "ONBOARDAI_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
            simulate_it_failure=os.getenv("ONBOARDAI_SIMULATE_IT_FAILURE", "false").lower()
            == "true",
        )
        settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        settings.drafts_dir.mkdir(parents=True, exist_ok=True)
        return settings


def langsmith_status() -> dict[str, bool | str]:
    """Return trace configuration without ever exposing secret values."""

    return {
        "api_key_present": bool(os.getenv("LANGSMITH_API_KEY")),
        "current_tracing_flag": os.getenv("LANGSMITH_TRACING", "").lower() == "true",
        "course_tracing_flag": os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true",
        "project": os.getenv("LANGSMITH_PROJECT", "onboardai-capstone"),
    }
