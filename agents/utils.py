"""Utility functions for agent LLM configuration."""

import os
import logging
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

def get_llm(model_key: str = "LLM_MODEL", default_model: str = "qwen2.5vl") -> ChatOpenAI | ChatOllama:
    """Retrieve an LLM instance based on environment configuration.
    
    Args:
        model_key: The environment variable key for the model name (e.g., LLM_MODEL, LLM_MODEL_VALIDATION).
        default_model: The default model name if the key is not found.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model_name = os.getenv(model_key, default_model)
    
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # Strip /v1 if present for ChatOllama
        base_url = base_url.replace("/v1/", "").replace("/v1", "")
        logger.info("Using Ollama LLM (%s) for %s at: %s", model_name, model_key, base_url)
        return ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0,
        )
    else:
        logger.info("Using OpenAI LLM (%s) for %s", model_name, model_key)
        # Standard OpenAI client
        return ChatOpenAI(
            model=model_name if model_name and "gpt" in model_name else "gpt-4o-mini",
            temperature=0,
        )
