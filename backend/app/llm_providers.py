"""Local-model (Ollama) fallback for /api/refine and /api/ask — opt-in, clearly-degraded
alternative to the primary Anthropic (Claude) path in routers/refine.py and routers/ask.py.

Claude stays PRIMARY. This module is only ever reached when a caller explicitly asks for it
(RefineRequest/AskRequest.provider == "ollama") AND the deployment has opted in via
settings.llm_provider == "ollama" (config.py) — mirroring the "lazy API key prompt, works
without a key, degrades gracefully" pattern already established in index.html (see
getApiKey()/renderRefineKeyPrompt() there): a user with no Anthropic key isn't blocked, but
they get something visibly lower-confidence, never presented with the same authority as a
Claude-backed answer. Every response produced via this path is labeled `provider: "ollama"`
in schemas.RefineResponse/AskResponse specifically so the frontend (or any API consumer) can
render it differently — this module never claims to be the primary path.

REAL TEST RESULTS this design is based on (see backend/README.md's "Local-model fallback"
section for the full write-up; run yourself via a throwaway script hitting
http://localhost:11434/api/chat with REFINEMENT_TOOL to reproduce):

  Structured tool-calling reliability against the exact REFINEMENT_TOOL schema, 3 requirement/
  recommendation cases x 3 repeated runs each (9 calls per model), num_ctx explicitly set to
  8192 (both models' native context is 32768; the prompt here is a few hundred tokens — Ollama's
  small default num_ctx was ruled out as a confound, not assumed away):

    qwen2.5:7b, native tool_calls only:        8/9  (89%)
    mistral:latest, native tool_calls only:    4/9  (44%) — mistral's Ollama chat template
      frequently emits the function call as JSON text in the message *content* instead of the
      structured tool_calls field, even though the API nominally "supports" tools.
    qwen2.5:7b,   native + fallback JSON parse of content:   8/9  (89%, one genuine empty-
      content failure)
    mistral:latest, native + fallback JSON parse of content: 9/9 (100% across the 3 sampled
      runs; not claimed as a guaranteed rate at larger sample sizes)

  Conclusion: neither model reliably emits well-formed tool_calls alone, but both are reliable
  enough to ship IF the caller also parses JSON out of free-form content as a fallback when
  tool_calls is empty or malformed — which is exactly what _extract_tool_result() below does.
  This is not "true native function calling" — it is prompt-engineered structured output with
  a schema-validating parse layer, same spirit as the guardrail this whole app's rule-engine-
  first design already embodies. Shipped as a REAL fallback (not narrowed to /api/ask-only)
  specifically because the measured combined reliability (native-or-fallback) was ~89-100%,
  not because it was assumed to work.

/api/ask does not need tool-calling at all (it returns prose, same as the Claude path) so its
local path is a plain chat completion — inherently lower-risk than the schema-constrained
refine path.
"""
import json
import re

import httpx
from fastapi import HTTPException

REQUIRED_REFINEMENT_KEYS = ("adjusted_picks", "rationale", "open_questions")

# Prepended to every local-model rationale/answer so the degraded-quality label survives even
# if a caller only renders `rationale`/`answer` and ignores the `provider` field on the
# response schema. Matches the blunt, inline-error tone index.html already uses for its own
# degraded states (e.g. the `.refine-error` div rendered on a failed /api/refine call) rather
# than a softer marketing-style disclaimer.
LOCAL_MODEL_DISCLAIMER = (
    "[Local model — offline/degraded mode, not Claude. Lower reliability than the "
    "Claude-backed path; verify anything load-bearing.] "
)


def check_model_available(base_url: str, model: str) -> None:
    """Fails fast and clearly if the configured Ollama model isn't actually pulled, rather
    than letting a confusing 404 from Ollama's own API surface as an opaque 502. Called once
    per request rather than cached — this is a local dev/self-host feature, not a hot path
    that needs to avoid a cheap localhost HTTP call."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
        resp.raise_for_status()
        installed = {m["name"] for m in resp.json().get("models", [])}
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Local model fallback is enabled (LLM_PROVIDER=ollama) but the Ollama "
                f"daemon at {base_url} could not be reached: {exc}. Is `ollama serve` running?"
            ),
        ) from exc
    if model not in installed and not any(m.startswith(model + ":") for m in installed):
        raise HTTPException(
            status_code=503,
            detail=(
                f"Configured OLLAMA_MODEL='{model}' is not installed on the Ollama daemon at "
                f"{base_url}. Installed models: {sorted(installed) or '(none)'}. Run "
                f"`ollama pull {model}` first, or change OLLAMA_MODEL to an installed model."
            ),
        )


def _extract_tool_result(message: dict) -> dict | None:
    """Native tool_calls first; if absent/malformed, regex-scan message content for an
    embedded JSON object/array carrying the same required keys — see module docstring for the
    real pass-rate data this two-path strategy is based on."""
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        if fn.get("name") != "submit_refinement":
            continue
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = None
        if isinstance(args, dict) and all(k in args for k in REQUIRED_REFINEMENT_KEYS):
            return args

    content = message.get("content") or ""
    for candidate in re.findall(r"\{.*\}", content, re.DOTALL):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            if "arguments" in parsed and isinstance(parsed["arguments"], dict):
                args = parsed["arguments"]
                if all(k in args for k in REQUIRED_REFINEMENT_KEYS):
                    return args
            elif all(k in parsed for k in REQUIRED_REFINEMENT_KEYS):
                return parsed
    for candidate in re.findall(r"\[.*\]", content, re.DOTALL):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            args = parsed[0].get("arguments")
            if isinstance(args, dict) and all(k in args for k in REQUIRED_REFINEMENT_KEYS):
                return args
    return None


def run_ollama_refinement(
    base_url: str,
    model: str,
    system_prompt: str,
    refinement_tool: dict,
    requirement_text: str,
    recommendations: dict,
    grounding: str,
) -> tuple[dict, dict]:
    """Local-model equivalent of routers/refine.py's _run_refinement(). Retries once (a fresh
    sample, not a repeat of the same failed output) on extraction failure before giving up —
    the measured per-call failure modes above were sporadic, not deterministic, so one retry
    meaningfully raises effective reliability without masking a systematic problem (a second
    consecutive failure still surfaces as a 502)."""
    check_model_available(base_url, model)

    ollama_tool = {
        "type": "function",
        "function": {
            "name": refinement_tool["name"],
            "description": refinement_tool["description"],
            "parameters": refinement_tool["input_schema"],
        },
    }
    user_content = (
        f"Requirement text:\n{requirement_text}\n\n"
        f"Rule engine recommendations (JSON):\n{json.dumps(recommendations)}{grounding}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "tools": [ollama_tool],
        "stream": False,
        "options": {"num_ctx": 8192},
    }

    last_error = None
    for _attempt in range(2):
        try:
            resp = httpx.post(f"{base_url.rstrip('/')}/api/chat", json=payload, timeout=120.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail=f"Local Ollama model call failed: {exc}"
            ) from exc
        data = resp.json()
        message = data.get("message", {})
        result = _extract_tool_result(message)
        if result is not None:
            usage = {
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            }
            result["rationale"] = LOCAL_MODEL_DISCLAIMER + result.get("rationale", "")
            return result, usage
        last_error = message.get("content", "")[:300]

    raise HTTPException(
        status_code=502,
        detail=(
            f"Local model '{model}' did not return a valid structured refinement after 2 "
            f"attempts (last raw output: {last_error!r}). Try again, or use the Claude-backed "
            f"path instead."
        ),
    )


def run_ollama_ask(base_url: str, model: str, system_prompt: str, history: list[dict]) -> tuple[str, dict]:
    """Local-model equivalent of routers/ask.py's _run_ask(). No structured-output constraint
    here (see module docstring) — /api/ask returns prose either way, so this is a plain chat
    completion, inherently lower-risk than the schema-constrained refine path."""
    check_model_available(base_url, model)

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + history,
        "stream": False,
        "options": {"num_ctx": 8192},
    }
    try:
        resp = httpx.post(f"{base_url.rstrip('/')}/api/chat", json=payload, timeout=120.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Local Ollama model call failed: {exc}") from exc

    data = resp.json()
    answer = data.get("message", {}).get("content", "")
    if not answer:
        raise HTTPException(status_code=502, detail="Local model returned an empty answer.")
    usage = {
        "input_tokens": data.get("prompt_eval_count", 0),
        "output_tokens": data.get("eval_count", 0),
    }
    return LOCAL_MODEL_DISCLAIMER + answer, usage
