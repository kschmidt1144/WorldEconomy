"""Multi-provider LLM access for the cross-checking panel.

Each model is reached over its REST API with `requests` (no vendor SDKs), so
adding a provider is a registry line. Keys are read from the environment or the
gitignored `.env` — never persisted, never printed. Only providers whose key is
present are "available"; the panel degrades gracefully, exactly like the FRED
connector.

Model strings and base URLs are all overridable via env (PANEL_<NAME>_MODEL /
PANEL_<NAME>_BASE) so a provider that renames a model doesn't break the panel.

Free routes (no cost, just a signup): GitHub Models (`GITHUB_TOKEN`) gives
free GPT-4o/-mini; Groq (`GROQ_API_KEY`) gives free Llama-3.3, DeepSeek-distill,
Qwen; Google AI Studio (`GOOGLE_API_KEY`) has a free Gemini tier; Mistral
(`MISTRAL_API_KEY`) and OpenRouter (`OPENROUTER_API_KEY`, several `:free`
models) round out the breadth.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import requests

from ..config import ROOT


def _get_key(*names: str) -> str | None:
    """Resolve a key from env (any case) or the .env file. Never logged."""
    for n in names:
        v = os.environ.get(n) or os.environ.get(n.upper()) or os.environ.get(n.lower())
        if v:
            return v.strip()
    envf = ROOT / ".env"
    if envf.exists():
        wanted = {n.lower() for n in names}
        for line in envf.read_text().splitlines():
            k, sep, val = line.partition("=")
            if sep and k.strip().lower() in wanted:
                return val.strip().strip("'\"")
    return None


def _env_model(name: str, default: str) -> str:
    return os.environ.get(f"PANEL_{name.upper().replace('-', '_')}_MODEL", default)


def _env_base(name: str, default: str) -> str:
    return os.environ.get(f"PANEL_{name.upper().replace('-', '_')}_BASE", default)


@dataclass
class Provider:
    name: str                       # friendly id, e.g. "claude"
    label: str                      # display, e.g. "Claude (Anthropic)"
    kind: str                       # "anthropic" | "google" | "openai"
    model: str
    key_names: tuple[str, ...]
    base_url: str = ""
    tier: str = "free"              # "free" | "paid" — informational
    key_names_shown: tuple[str, ...] = field(default_factory=tuple)

    def key(self) -> str | None:
        return _get_key(*self.key_names)

    def available(self) -> bool:
        return bool(self.key())


# The default roster. Order = display order. Covers the frontier labs the user
# named (Claude, Gemini, GPT, Grok) plus free breadth from different lineages:
# open US (Llama), Chinese (DeepSeek, Qwen), European (Mistral).
def _registry() -> dict[str, Provider]:
    r: dict[str, Provider] = {}

    def add(p: Provider):
        r[p.name] = p

    # key_names include short aliases so the project's .env convention works
    # (e.g. `groq_api` like the existing `fred_api`); matching is case-insensitive.
    groq = ("GROQ_API_KEY", "GROQ_API", "GROQ")
    add(Provider("claude", "Claude (Anthropic)", "anthropic",
                 _env_model("claude", "claude-haiku-4-5"),
                 ("ANTHROPIC_API_KEY", "ANTHROPIC_API", "ANTHROPIC", "CLAUDE_API_KEY", "CLAUDE"),
                 tier="paid"))
    add(Provider("gemini", "Gemini (Google)", "google",
                 _env_model("gemini", "gemini-2.5-flash"),
                 ("GOOGLE_API_KEY", "GOOGLE_API", "GEMINI_API_KEY", "GEMINI_API", "GEMINI"), tier="paid"))
    # free GPT via GitHub Models (Azure-hosted, OpenAI-compatible)
    add(Provider("gpt", "GPT-4o-mini (GitHub Models, free)", "openai",
                 _env_model("gpt", "gpt-4o-mini"), ("GITHUB_TOKEN", "GITHUB_API", "GH_TOKEN"),
                 base_url=_env_base("gpt", "https://models.inference.ai.azure.com"), tier="free"))
    # paid OpenAI, if a real OpenAI key is present
    add(Provider("gpt-openai", "GPT-4o-mini (OpenAI)", "openai",
                 _env_model("gpt_openai", "gpt-4o-mini"), ("OPENAI_API_KEY", "OPENAI_API", "OPENAI"),
                 base_url=_env_base("gpt_openai", "https://api.openai.com/v1"), tier="paid"))
    add(Provider("grok", "Grok (xAI)", "openai",
                 _env_model("grok", "grok-2-latest"),
                 ("XAI_API_KEY", "XAI_API", "XAI", "GROK_API_KEY", "GROK_API", "GROK"),
                 base_url=_env_base("grok", "https://api.x.ai/v1"), tier="paid"))
    # free open-weights via Groq — one key, three lineages (Meta / Alibaba / OpenAI)
    add(Provider("llama", "Llama-3.3-70B (Groq, free)", "openai",
                 _env_model("llama", "llama-3.3-70b-versatile"), groq,
                 base_url=_env_base("groq", "https://api.groq.com/openai/v1"), tier="free"))
    add(Provider("qwen", "Qwen3 (Groq, free)", "openai",
                 _env_model("qwen", "qwen/qwen3.6-27b"), groq,
                 base_url=_env_base("groq", "https://api.groq.com/openai/v1"), tier="free"))
    add(Provider("gpt-oss", "GPT-OSS-120B (Groq, free)", "openai",
                 _env_model("gpt_oss", "openai/gpt-oss-120b"), groq,
                 base_url=_env_base("groq", "https://api.groq.com/openai/v1"), tier="free"))
    # DeepSeek left Groq; reach it via its own API (cheap) if you have a key
    add(Provider("deepseek", "DeepSeek (deepseek.com)", "openai",
                 _env_model("deepseek", "deepseek-chat"), ("DEEPSEEK_API_KEY", "DEEPSEEK_API", "DEEPSEEK"),
                 base_url=_env_base("deepseek", "https://api.deepseek.com"), tier="paid"))
    add(Provider("mistral", "Mistral Large (free tier)", "openai",
                 _env_model("mistral", "mistral-large-latest"), ("MISTRAL_API_KEY", "MISTRAL_API", "MISTRAL"),
                 base_url=_env_base("mistral", "https://api.mistral.ai/v1"), tier="free"))
    add(Provider("openrouter", "OpenRouter", "openai",
                 _env_model("openrouter", "deepseek/deepseek-chat-v3-0324:free"),
                 ("OPENROUTER_API_KEY", "OPENROUTER_API", "OPENROUTER"),
                 base_url=_env_base("openrouter", "https://openrouter.ai/api/v1"), tier="free"))
    return r


PROVIDERS = _registry()


def available_providers() -> list[Provider]:
    """Registry members whose key is present (re-read each call for freshness)."""
    global PROVIDERS
    PROVIDERS = _registry()
    return [p for p in PROVIDERS.values() if p.available()]


def _strip_reasoning(text: str) -> str:
    """Remove <think>…</think> blocks that reasoning-distill models emit."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def ask(provider: Provider, prompt: str, system: str = "", *, timeout: int = 60,
        max_tokens: int = 1400) -> str:  # headroom for reasoning models (Qwen3/GPT-OSS/R1)
    """Send one prompt to one provider; return its text. Raises on error."""
    key = provider.key()
    if not key:
        raise RuntimeError(f"{provider.name}: no API key configured")

    if provider.kind == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": provider.model, "max_tokens": max_tokens,
                  **({"system": system} if system else {}),
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        r.raise_for_status()
        return _strip_reasoning("".join(b.get("text", "") for b in r.json()["content"]))

    if provider.kind == "google":
        body: dict = {"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{provider.model}:generateContent",
            params={"key": key}, json=body, timeout=timeout,
        )
        r.raise_for_status()
        cand = r.json()["candidates"][0]
        return _strip_reasoning("".join(p.get("text", "") for p in cand["content"]["parts"]))

    # openai-compatible (GitHub Models, Groq, xAI, OpenAI, Mistral, OpenRouter)
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    r = requests.post(
        f"{provider.base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={"model": provider.model, "messages": msgs, "max_tokens": max_tokens,
              "temperature": 0.2},
        timeout=timeout,
    )
    r.raise_for_status()
    return _strip_reasoning(r.json()["choices"][0]["message"]["content"])
