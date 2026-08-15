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
import logging

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

REQUIRED_REFINEMENT_KEYS = ("adjusted_picks", "rationale", "open_questions")

# SECURITY: the fallback JSON-parse path below reads a tool call out of free-form model
# *content* instead of the structured tool_calls field. That content is not a trusted channel —
# it's produced by a model that may have RAG-grounding text (docs/use-case-knowledge-base/) or
# KB `note` fields (stack-kb.json, embedded in index.html and surfaced via the KB-MCP work)
# concatenated into its context. A `note` field containing something shaped like
# {"name": "submit_refinement", "arguments": {...}} does not need to persuade the model to
# *decide* to call a tool — it only needs the model to echo it back, which is a much lower bar
# than genuine prompt injection normally requires. Three mitigations, all applied below:
#   1. Only accept a fallback parse when the message content is EXCLUSIVELY the JSON object
#      (whitespace-trimmed) — no surrounding prose. A real model-authored tool call in content
#      is typically the whole message; injected/reflected JSON embedded inside other prose is
#      not. This alone rules out the common case of a `note`'s JSON snippet being echoed
#      mid-sentence rather than emitted as the complete response.
#   2. Allowlist the function name (submit_refinement is the only one ever offered to this
#      model) and schema-validate the arguments (required keys + types) before returning
#      anything — never dispatch on structural shape alone.
#   3. Log every fallback-parsed call distinctly from native tool_calls hits, so the two paths
#      are distinguishable in logs/metrics — this is also exactly the eval signal needed to
#      measure how often the fallback path fires in production, not just in the 9-call test batch.
ALLOWED_FUNCTION_NAME = "submit_refinement"

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


def _validate_refinement_shape(args: dict) -> bool:
    """Schema validation beyond "has the right keys" — cheap type checks that reject the
    shape of thing an echoed/injected JSON blob is likely to have (e.g. a `note` field's JSON
    fragment coerced to fit required-key membership but not real field types)."""
    if not all(k in args for k in REQUIRED_REFINEMENT_KEYS):
        return False
    if not isinstance(args.get("adjusted_picks"), list):
        return False
    if not isinstance(args.get("rationale"), str):
        return False
    if not isinstance(args.get("open_questions"), list):
        return False
    return True


def _extract_tool_result(message: dict) -> tuple[dict, str] | None:
    """Native tool_calls first (trusted channel — the model API's own structured field);
    only if that's absent/malformed, fall back to parsing message *content*. Returns
    (args, path) where path is "native" or "fallback" so callers can log/measure the two
    paths distinctly — see the SECURITY note above ALLOWED_FUNCTION_NAME for why the fallback
    path is deliberately much stricter than a generic JSON-in-text scan."""
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        if fn.get("name") != ALLOWED_FUNCTION_NAME:
            continue
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = None
        if isinstance(args, dict) and _validate_refinement_shape(args):
            return args, "native"

    # Fallback: content must be EXCLUSIVELY a JSON object once whitespace-trimmed — not a
    # regex scan for any brace-delimited substring anywhere in a larger blob of prose. A real
    # model-authored tool call emitted via content is normally the entire message; JSON that
    # merely appears somewhere inside other text (e.g. reflected from a KB `note` field it was
    # grounded on) is exactly the shape a reflection-based injection would produce, and this
    # check rejects it outright rather than trying to distinguish intent after the fact.
    content = (message.get("content") or "").strip()
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        candidate = parsed.get("arguments") if isinstance(parsed.get("arguments"), dict) else parsed
        name = parsed.get("name")
        # If the blob carries a "name" field (i.e. it's shaped like a tool-call envelope, not
        # bare arguments), it must match the one function this model was ever offered.
        if name is not None and name != ALLOWED_FUNCTION_NAME:
            logger.warning("Rejected fallback-parsed content: name=%r does not match allowlist", name)
            return None
        if isinstance(candidate, dict) and _validate_refinement_shape(candidate):
            return candidate, "fallback"
    elif isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        item = parsed[0]
        if item.get("name") not in (None, ALLOWED_FUNCTION_NAME):
            logger.warning("Rejected fallback-parsed content: name=%r does not match allowlist", item.get("name"))
            return None
        args = item.get("arguments")
        if isinstance(args, dict) and _validate_refinement_shape(args):
            return args, "fallback"

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
        extracted = _extract_tool_result(message)
        if extracted is not None:
            result, path = extracted
            # Distinct log line per path — this is the eval signal the security review asked
            # for: how often does production actually rely on the (riskier, stricter-checked)
            # fallback path versus native tool_calls. Not just a 9-call test-batch statistic.
            logger.info("Ollama refinement extraction path=%s model=%s", path, model)
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
