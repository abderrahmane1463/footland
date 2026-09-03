"""
components/llm.py — Shared LLM provider layer (DeepSeek primary, Groq fallback).

Both AI features in the dashboard — the analysis reports and the chatbot — go
through complete(). Keeping one implementation matters because the provider
quirks below are easy to get wrong and expensive to debug twice.

Provider notes, all found by testing rather than assuming:

- The DeepSeek model is "deepseek-v4-flash", not "deepseek-chat" (that name no
  longer exists) and not "v4-pro". Pro spends its budget reasoning — 4 773
  reasoning tokens for LESS output than flash — takes over two minutes, and
  returns a completely empty message at max_tokens=3000.
- These are reasoning models: part of max_tokens is spent thinking before any
  visible text is produced. Too small a budget yields an empty message rather
  than a short answer, so callers must give real headroom.
- Token budgets differ per provider. DeepSeek needs room; Groq rejects large
  ceilings outright with HTTP 413 Payload Too Large.
- Groq's free tier rate-limits under real use (429), hence the backoff.
"""

import os
import time

import requests
import streamlit as st

try:
    from groq import Groq
except ImportError:  # pragma: no cover - groq may not be installed yet
    Groq = None


DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# Primary then a smaller fallback used on rate limits. The llama-3.x models
# that used to be here were decommissioned by Groq (404 model_not_found).
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

# A full report takes about 30 s on DeepSeek, so 90 s is generous headroom.
# It used to be 180 s with three attempts, which meant a stalled request could
# hold the spinner for nine minutes before even trying the fallback — fine for
# a background job, unacceptable behind a UI someone is waiting on.
REQUEST_TIMEOUT = 90
MAX_ATTEMPTS = 2


# ─── Key resolution ───────────────────────────────────────────────────────────
def _secret_or_env(name: str) -> str | None:
    """Read a credential from st.secrets first, then the environment."""
    try:
        value = st.secrets[name]
        if value:
            return value
    except Exception:  # noqa: BLE001 - secrets file may not exist at all
        pass
    return os.environ.get(name)


def get_deepseek_key() -> str | None:
    return _secret_or_env("DEEPSEEK_API_KEY")


def get_groq_key() -> str | None:
    return _secret_or_env("GROQ_API_KEY")


# ─── Providers ────────────────────────────────────────────────────────────────
def call_deepseek(messages: list[dict], max_tokens: int,
                  temperature: float = 0.4) -> str:
    """Primary provider. Returns "" when unavailable so the caller falls back."""
    key = get_deepseek_key()
    if not key:
        return ""

    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = requests.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if resp.status_code == 402:
                # Prepaid balance exhausted — retrying won't help, fall back.
                print("DEBUG llm: DeepSeek balance exhausted")
                return ""
            if resp.status_code in (401, 403):
                # Bad or revoked key — retrying won't help either.
                print(f"DEBUG llm: DeepSeek auth rejected ({resp.status_code})")
                return ""
            resp.raise_for_status()
            return (resp.json()["choices"][0]["message"]["content"] or "").strip()
        except requests.exceptions.ReadTimeout as exc:
            # The request was accepted but the model never answered within the
            # budget. Retrying means waiting the full timeout again for the same
            # likely outcome, so fall through to the fallback provider instead —
            # it answers in about three seconds.
            print(f"DEBUG llm: DeepSeek read timeout after {REQUEST_TIMEOUT}s: {exc}")
            return ""
        except requests.exceptions.RequestException as exc:
            # Connection-level failures (DNS, refused, dropped) fail within
            # seconds and usually clear immediately, so retrying is cheap and
            # worthwhile — without it a one-second blip silently demotes the
            # user to the fallback model.
            print(f"DEBUG llm: DeepSeek network error (attempt {attempt + 1}): {exc}")
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(2 * (attempt + 1))
                continue
        except Exception as exc:  # noqa: BLE001 - malformed response, etc.
            print(f"DEBUG llm: DeepSeek failed: {exc}")
            return ""
    return ""


def call_groq(messages: list[dict], max_tokens: int,
              temperature: float = 0.4) -> str:
    """Fallback provider. Returns "" when unavailable."""
    key = get_groq_key()
    if not key or Groq is None:
        return ""

    client = Groq(api_key=key)
    for model in GROQ_MODELS:
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
                break  # empty reply ⇒ next model, not the same one again
            except Exception as exc:  # noqa: BLE001
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(3 * (attempt + 1))
                    continue
                print(f"DEBUG llm: Groq {model} failed: {exc}")
                break
    return ""


def complete(messages: list[dict], *, deepseek_max_tokens: int,
             groq_max_tokens: int, temperature: float = 0.4) -> str:
    """Run a completion through DeepSeek, falling back to Groq.

    Returns "" if every provider failed — callers decide how to surface that.

    The two token budgets are separate on purpose: DeepSeek needs headroom for
    its reasoning pass, while Groq rejects the same ceiling with HTTP 413.
    """
    content = call_deepseek(messages, deepseek_max_tokens, temperature)
    if content:
        return content
    return call_groq(messages, groq_max_tokens, temperature)


def any_provider_configured() -> bool:
    """True when at least one provider has a usable key."""
    return bool(get_deepseek_key()) or bool(get_groq_key() and Groq is not None)
