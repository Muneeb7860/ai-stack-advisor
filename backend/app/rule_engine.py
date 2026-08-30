"""Python port of the v1 rule engine (index.html's stripNegations()/detectSignals()/pickX()
functions), for use by app/mcp/server.py's recommend_stack() tool.

PORT DISCIPLINE (per the decision already made — see KICKOFF_BRIEF.md and docs/adr/0001):
this is a faithful transliteration of index.html's JavaScript, not a re-derivation from first
principles. index.html went through two expansion/validation passes (see
../validation-report.md and KICKOFF_BRIEF.md Section 0) that found and fixed real bugs —
negation handling, on-prem/air-gapped support, warehouse detection, team-size conflicts, a
live-quiz-app messaging/database bug, several category-card-contradiction audit fixes (see
inline "AUDIT FIX" comments throughout index.html's vendor-comparison functions). index.html's
CURRENT source has all of those fixes baked in, so porting it as-is carries them over
automatically. Do not "clean up" or "simplify" any branch below without checking it against
index.html's actual current logic first.

Source of truth: index.html's <script> block, functions stripNegations() through
pickGovernance() (roughly lines 352–1180 as of this port, 47 pickX functions across signal
detection, core stack, vendor-alternatives comparisons, AI-serving architecture, trade-offs,
and cost/governance). Two independent implementations of the same logic (JS for the
zero-backend v1 product, Python for the MCP tool) — not one importing the other, since v1 must
stay fully client-side (PRD NFR-1/NFR-5). Re-verified byte-for-byte against the live JS after
each expansion pass — see docs/adr/0001-mcp-rule-engine-port.md for the verification method.

Naming: JS object keys (camelCase, e.g. `s.onPrem`) are kept AS-IS in the `signals` dict
returned by detect_signals() — not snake_cased — specifically so this stays a mechanical,
diffable port against index.html. Function/module names are snake_case per Python convention;
signal dict keys and vendor-table dict keys (id/name/cat/bestFor/strength/drawback/pricing)
are not, for the same diffability reason.
"""
import re

# ---------- Signal detection ----------


# Clause boundary shared by the active-voice negation regexes and stripNegations(): allow
# comma-separated lists ("no website, API, database, cloud, ...") to stay inside ONE clause —
# stopping at the first comma (the old behavior) truncated "I do not need a website, API,
# database, ..., or a vector database." after just "website", leaving every later item to be
# read as a positive mention. Stop only at a true sentence end, or at a subordinating/
# contrasting conjunction, so a later, unrelated positive requirement in the SAME sentence
# ("...but we do need Postgres for durability") is never swept into the negated clause.
_CLAUSE_END = r"(?=\s+(?:because|since|but|however|whereas|although|while)\b|[.!?;\n]|$)"

# Passive-voice negation phrases ("Kubernetes must not be used") — the excluded subject sits
# BEFORE the negation phrase here, which the active-voice "no|not|..." regexes can never see
# (they only look forward from the negator word). Handled as a second, independent pattern
# rather than folded into the active one, since the grammar runs the opposite direction.
_PASSIVE_NEGATION_PHRASES = (
    "must not be used", "cannot be used", "can't be used", "should not be used",
    "is not allowed", "are not allowed", "is not needed", "are not needed",
    "is not required", "are not required", "is excluded", "are excluded",
    "not permitted", "not to be used", "is ruled out", "are ruled out",
)
_PASSIVE_NEGATION_ALT = "|".join(_PASSIVE_NEGATION_PHRASES)


def strip_negations(text: str) -> str:
    """Mirrors index.html's stripNegations() exactly.

    Passive-voice clauses are stripped FIRST: "Kubernetes must not be used" would otherwise have
    its "not be used" tail consumed by the active-voice pass (which fires on the bare word
    "not"), leaving nothing left for the passive pattern to match against and "Kubernetes"
    behind in the text.
    """
    text = re.sub(
        r"[^.!?;\n]{0,300}?\b(?:" + _PASSIVE_NEGATION_ALT + r")\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # "Neither Java nor Python should be used" — the excluded items sit AFTER "neither", but
    # the active-voice pass above never fires on "neither" at all (not in its negator list), so
    # without this, both names survive to be read as positive mentions. See _NEITHER_NOR_CLAUSE.
    text = re.sub(
        r"\bneither\b[^.!?;\n]{0,300}?" + _CLAUSE_END,
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(no|not|without|avoid|don't|doesn't|isn't|won't|never|excluding|except for|except)\b"
        r"[^.!?;\n]{0,300}?" + _CLAUSE_END,
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return text


EXCLUSION_TERMS = {
    "kubernetes": ["kubernetes", "k8s", "eks", "gke", "aks"],
    "containers": ["docker", "container", "containers", "containerisation", "containerization"],
    "microservices": ["microservice", "microservices"],
    "messaging": ["kafka", "rabbitmq", "message queue", "messaging", "event bus", "pub/sub"],
    "cache": ["cache", "caching", "redis", "memcached", "valkey"],
    "database": ["database", "db", "postgres", "postgresql", "mysql", "mongodb", "mongo", "datastore"],
    "cloud": ["cloud", "aws", "azure", "gcp", "google cloud", "huawei"],
    "llm": ["llm", "llms", "large language model", "gpt", "claude", "openai", "genai", "generative ai"],
    "rag": ["rag", "retrieval augmented", "retrieval-augmented", "vector database", "vector db", "embedding", "embeddings"],
    "frontend": ["website", "web app", "web application", "web site", "frontend", "front-end", "ui", "react", "angular", "vue"],
    "api": ["api", "apis", "rest api", "backend service", "web service", "endpoint"],
    "serverless": ["serverless", "lambda"],
    "mesh": ["service mesh", "istio", "linkerd"],
    "iam": ["sso", "okta", "identity provider", "auth0"],
    "observability": ["observability", "monitoring", "datadog", "splunk"],
    # Found via a manual "neither Java nor Python" QA scenario: no language terms existed in
    # this table at all, so no phrasing of "don't use Java" could ever exclude it, independent
    # of how well the negation-clause regex itself worked. Deliberately excludes the bare word
    # "go" (unlike KNOWN_TERMS's own careful padded " go " — every use here already runs through
    # \b...\b, which wouldn't respect padding anyway) — "go" alone is too common in ordinary
    # English ("we don't want to go slow") to safely treat as a language-exclusion trigger.
    "languages": ["java", "python", "javascript", "typescript", "ruby", "php", "kotlin", "swift", "rust", "c#", ".net", "node.js", "nodejs"],
}

_NEGATION_CLAUSE = re.compile(
    r"\b(?:no|not|without|avoid|don't|doesn't|isn't|won't|never|excluding|except for|except)\b"
    r"([^.!?;\n]{0,300}?)" + _CLAUSE_END,
    re.I,
)
_PASSIVE_NEGATION_CLAUSE = re.compile(
    r"([^.!?;\n]{0,300}?)\b(?:" + _PASSIVE_NEGATION_ALT + r")\b",
    re.I,
)
# "Neither Java nor Python" — a correlating conjunction, not a single negator word, so it needs
# its own pattern rather than folding into _NEGATION_CLAUSE above. Capturing straight through to
# the clause boundary naturally includes everything after "nor" too, comma lists included.
_NEITHER_NOR_CLAUSE = re.compile(r"\bneither\b([^.!?;\n]{0,300}?)" + _CLAUSE_END, re.I)


# A negator followed by one of these qualifies what comes next rather than prohibiting it.
# "We need not only a website but also a mobile app" ASKS FOR a website; reading it as an
# exclusion deleted the Frontend recommendation outright — worse than the over-recommendation
# this mechanism exists to prevent. Same for "not just a database problem" and the quantity
# forms "no more than 200ms" / "no fewer than three regions".
NON_EXCLUSION_QUALIFIERS = (
    "only", "just", "merely", "simply", "solely", "exclusively",
    "more than", "less than", "fewer than", "later than", "earlier than", "greater than",
)

# Found via a manual "we already use Postgres, don't need ANOTHER database" QA scenario: this
# phrase means "one already exists, decline a second" — the opposite of "exclude the category
# entirely" — but the qualifying word sits immediately before the EXCLUDED TERM itself ("another
# database"), not at the start of the whole clause like NON_EXCLUSION_QUALIFIERS above ("not
# only a website..."), so a clause-level startswith() check can't catch it. Checked per-term-
# match instead, against the text immediately preceding that specific match.
_QUANTITY_QUALIFIER_RE = re.compile(r"\b(?:another|a second|an additional|a different|one more)\s*$", re.I)


def _record_exclusions(clause: str, out: dict, terms_by_key: dict | None = None) -> None:
    """Shared by every negation pattern (active, passive, neither/nor) — records every
    EXCLUSION_TERMS key found in `clause`, skipping a match immediately preceded by a
    quantity-qualifier ("another", "a second", ...). When `terms_by_key` is given, also
    records exactly which literal term matched per key — detect_exclusions() itself never
    needs this (a plain boolean is enough to decide whether to overwrite a pick), but picking
    a real language ALTERNATIVE (see _pick_language_alternative) needs to know exactly which
    language(s) were named, so as not to recommend one the user also just ruled out."""
    for key, terms in EXCLUSION_TERMS.items():
        for term in terms:
            m = re.search(r"\b" + re.escape(term) + r"\b", clause)
            if m and not _QUANTITY_QUALIFIER_RE.search(clause[: m.start()]):
                out[key] = True
                if terms_by_key is not None:
                    terms_by_key.setdefault(key, set()).add(term)
                # No `break` here: a single clause can legitimately name MULTIPLE distinct
                # terms in the same category ("neither Java, Python, nor JavaScript") — found
                # via review of this exact scenario, where an early break after the FIRST
                # matching term ("java") silently dropped "javascript" from terms_by_key,
                # letting the alternative-picker recommend a language the user also excluded.
                # detect_exclusions()'s own boolean-only callers are unaffected either way
                # (out[key] = True is idempotent), so this is free for them.


def _find_exclusions(text: str, terms_by_key: dict | None = None) -> dict:
    """Mirrors index.html's detectExclusions(): keeps what strip_negations() throws away.

    strip_negations() deletes the negated clause so "no compliance requirements" cannot fire a
    positive compliance signal — necessary, but it also discarded the only place the user said
    what they DON'T want, which is why "we must not use Kubernetes" still returned Kubernetes.
    """
    out = {}
    t = str(text or "").lower()
    for m in _NEGATION_CLAUSE.finditer(t):
        clause = m.group(1) or ""
        if clause.strip().startswith(NON_EXCLUSION_QUALIFIERS):
            continue
        _record_exclusions(clause, out, terms_by_key)
    # Passive voice ("Kubernetes must not be used") — see _PASSIVE_NEGATION_PHRASES above.
    for m in _PASSIVE_NEGATION_CLAUSE.finditer(t):
        _record_exclusions(m.group(1) or "", out, terms_by_key)
    # "Neither Java nor Python" — see _NEITHER_NOR_CLAUSE above.
    for m in _NEITHER_NOR_CLAUSE.finditer(t):
        _record_exclusions(m.group(1) or "", out, terms_by_key)
    return out


def detect_exclusions(text: str) -> dict:
    """Public entry point — see _find_exclusions() above for the actual implementation."""
    return _find_exclusions(text)


def detect_excluded_language_terms(text: str) -> set:
    """Which SPECIFIC language names (not just the "languages" category boolean) were named in
    a negated clause — used by _pick_language_alternative() to avoid recommending a language the
    user also explicitly ruled out, e.g. "neither Java, Python, nor Go"."""
    terms_by_key: dict = {}
    _find_exclusions(text, terms_by_key)
    return terms_by_key.get("languages", set())


KNOWN_TERMS = {
    "java": ["java", "spring boot"], "python": ["python", "django", "flask", "fastapi"], "go": ["golang", " go "],
    "node": ["node.js", "nodejs", "express.js", "nestjs"], "dotnet": [".net", "c#", "asp.net"],
    "ruby": ["ruby", "rails"], "php": ["php", "laravel"],
    "postgres": ["postgres", "postgresql"], "mysql": ["mysql"], "sqlServer": ["sql server", "mssql"],
    "oracleDb": ["oracle database", "oracle db"], "mongo": ["mongodb", "mongo"],
    "docker": ["docker"], "kubernetes": ["kubernetes", "k8s"], "openshift": ["openshift"],
    "react": ["react"], "angular": ["angular"], "vue": ["vue", "vue.js"],
    "datadog": ["datadog"], "prometheus": ["prometheus", "grafana"], "splunk": ["splunk"],
    "dynatrace": ["dynatrace"], "newrelic": ["new relic", "newrelic"], "elk": ["elk", "elastic stack", "elasticsearch"],
    "terraform": ["terraform"], "githubActions": ["github actions"], "jenkins": ["jenkins"],
    "gitlabCi": ["gitlab ci"], "circleci": ["circleci", "circle ci"], "azureDevops": ["azure devops"],
    "pinecone": ["pinecone"], "weaviate": ["weaviate"], "qdrant": ["qdrant"],
}

EXPERIENCE_BEFORE = ["we use", "we are using", "we're using", "we run", "we have", "we deploy", "we host",
    "our team knows", "our team uses", "team knows", "team uses", "experience with", "experienced with",
    "familiar with", "already on", "already use", "already using", "already run", "currently use",
    "currently using", "currently on", "our stack", "we know", "we standardise on", "we standardize on",
    "skilled in", "proficient in", "migrating from", "shop uses"]
EXPERIENCE_AFTER = ["experience", "expertise", "shop", "in production", "today", "already"]
EXPERIENCE_DISCLAIMERS = ["never used", "never worked", "no experience", "not familiar", "unfamiliar",
    "evaluating", "considering", "should we use", "thinking about", "looking at", "new to", "want to learn",
    "have not used", "haven't used", "no one knows", "nobody knows", "would like to use", "plan to use",
    "planning to use",
    # Statements of NON-use. Without these, "We don't use Kubernetes today" read as ownership: the
    # before-window "we don't use " does not contain "we use", so nothing disclaimed it, and the
    # after-window " today" hit EXPERIENCE_AFTER. Same defect as BUG-7, one phrasing over.
    "do not use", "don't use", "dont use", "no longer use", "no longer", "not using", "stopped using",
    "moving off", "migrating off", "away from", "do not run", "don't run", "not run on", "ruled out"]


def detect_known_tech(text: str, excluded: dict | None = None) -> dict:
    """Mirrors index.html's detectKnownTech(). `xxxMentioned` means the user NAMED a technology;
    this means they showed ownership of it. Conflating the two is what made "should we use
    Kubernetes? we have never used it before" claim the team already knew Kubernetes."""
    t = str(text or "").lower()
    out = {}
    for key, terms in KNOWN_TERMS.items():
        for term in terms:
            idx = t.find(term)
            while idx != -1:
                # Clip at sentence boundaries — without this, "We must not use Kubernetes. We
                # run PostgreSQL in production today." reads the next sentence's "in production
                # today" as Kubernetes ownership, on a sentence that excludes it.
                before = re.split(r"[.;!?]", t[max(0, idx - 60):idx])[-1]
                after = re.split(r"[.;!?]", t[idx + len(term): idx + len(term) + 40])[0]
                disclaimed = any(d in before or d in after for d in EXPERIENCE_DISCLAIMERS)
                if not disclaimed and (any(e in before for e in EXPERIENCE_BEFORE)
                                       or any(e in after for e in EXPERIENCE_AFTER)):
                    out[key] = True
                    break
                idx = t.find(term, idx + len(term))
            if out.get(key):
                break
    # Exclusion wins — "we ruled out Kubernetes" satisfying both reads is a contradiction the rest
    # of the engine has no way to resolve, so it is not representable.
    for k in (excluded or {}):
        out.pop(k, None)
    return out


_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

_LATENCY_RE = re.compile(
    r"(?:under|below|less than|within|at most|no more than|sub-?|<=?|max(?:imum)? of)\s*"
    r"([0-9]+(?:\.[0-9]+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
    r"(ms|millisecond|milliseconds|s|sec|secs|second|seconds|m|min|minute|minutes)\b")


def detect_latency_target(text: str):
    """Mirrors index.html's detectLatencyTarget(). detect_signals() had no numeric parsing at all,
    so an explicit "in under three seconds" requirement was dropped entirely."""
    best = None
    for m in _LATENCY_RE.finditer(str(text or "").lower()):
        raw = m.group(1)
        n = _WORD_NUMBERS.get(raw)
        if n is None:
            try:
                n = float(raw)
            except ValueError:
                continue
        unit = m.group(2)
        if unit == "ms" or unit.startswith("millisecond"):
            ms = n
        elif unit == "m" or unit.startswith("min"):
            ms = n * 60000
        else:
            ms = n * 1000
        if best is None or ms < best["ms"]:
            best = {"ms": ms, "text": m.group(0).strip()}
    return best


_CONCURRENCY_RE = re.compile(
    r"([0-9][0-9,.]*)\s*(k|m)?\s*(?:\+\s*)?(?:concurrent|simultaneous|parallel|peak|active)\s+"
    r"(?:users|sessions|connections|requests|clients)")

_TIMELINE_RE = re.compile(
    r"([0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)[\s-]*"
    r"(week|weeks|month|months|quarter|quarters|year|years)\b")

# A duration is only a DELIVERY window when something nearby says so. Without this check any
# "<n> months" phrase became a ship date: "Retain audit logs for 12 months" was exported into the
# ADR quality scenarios as "First production release ships inside <= 360 days" — a retention rule
# turned into a commitment the user never made, inside a decision record.
TIMELINE_CUES = ("timeline", "deadline", "deliver", "delivery", "launch", "ship", "release",
                 "go live", "go-live", "mvp", "milestone", "time frame", "timeframe", "build it",
                 "in production by", "due")
TIMELINE_DISQUALIFIERS = ("retain", "retention", "archive", "history", "historical", "logs for",
                          "keep", "stored for", "storage", "backlog", "experience", "warranty",
                          "contract", "licen")


def detect_concurrency_target(text: str):
    """Mirrors index.html's detectConcurrencyTarget(). "500 concurrent users" parsed to nothing —
    it does not even trip highScale, whose keywords are "high traffic"/"millions of users"."""
    best = None
    for m in _CONCURRENCY_RE.finditer(str(text or "").lower()):
        try:
            n = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if m.group(2) == "k":
            n *= 1e3
        elif m.group(2) == "m":
            n *= 1e6
        if best is None or n > best["count"]:
            best = {"count": n, "text": m.group(0).strip()}
    return best


def detect_timeline(text: str):
    """Mirrors index.html's detectTimeline(). Tightest stated window binds."""
    best = None
    t = str(text or "").lower()
    for m in _TIMELINE_RE.finditer(t):
        ctx = t[max(0, m.start() - 45): m.end() + 45]
        if any(d in ctx for d in TIMELINE_DISQUALIFIERS):
            continue
        if not any(c in ctx for c in TIMELINE_CUES):
            continue
        raw = m.group(1)
        n = _WORD_NUMBERS.get(raw, 12 if raw == "twelve" else None)
        if n is None:
            try:
                n = float(raw)
            except ValueError:
                continue
        unit = m.group(2)
        if unit.startswith("week"):
            days = n * 7
        elif unit.startswith("month"):
            days = n * 30
        elif unit.startswith("quarter"):
            days = n * 91
        else:
            days = n * 365
        if best is None or days < best["days"]:
            best = {"days": days, "text": m.group(0).strip()}
    return best


def excluded_pick(what: str) -> dict:
    """A pick the user explicitly ruled out — kept as a real card so the report shows the
    constraint was understood rather than silently producing a shorter stack."""
    return {
        "v": "Not recommended — you excluded " + what,
        "conf": "high",
        "excluded": True,
        "why": "Your requirement explicitly ruled this out, so nothing is recommended for this "
               "category. This is a stated constraint, not a heuristic default — if the exclusion "
               "was picked up in error, rephrase the requirement and re-run.",
    }


def domain_floor_pick(what: str, why: str) -> dict:
    """Same shape as excluded_pick(), but for a category the requirement's DOMAIN rules out
    rather than something the user explicitly said "no" to — different wording ("Not
    applicable" / inferred from what you described) since "you excluded X" would be misleading
    here."""
    return {"v": "Not applicable — " + what, "conf": "high", "excluded": True, "why": why}


# Found via a manual "...but also not on-prem" QA scenario: soft on-prem detection used to fire
# on the bare substring "on-prem"/"on premises" anywhere in the raw text, with zero awareness
# that the phrase itself might be negated — "not on-prem" recommended ON-PREM hosting for a
# requirement that explicitly ruled it out. strong_on_prem's own phrases ("no public cloud",
# "cannot use any public cloud") are deliberately left alone: the negation IS the signal there,
# by design, unlike the bare "on-prem" phrases here, where "on-prem" itself is the subject that
# can be negated.
_ON_PREM_NEGATED_BEFORE_RE = re.compile(
    r"\b(?:not|no|never|isn't|won't be|will not be|don't want|do not want|"
    r"doesn't want|does not want|avoid|without)\s*$", re.I
)


def _mentions_on_prem_unnegated(raw: str) -> bool:
    for term in ("on-prem", "on premises", "on-premise"):
        for m in re.finditer(re.escape(term), raw):
            if not _ON_PREM_NEGATED_BEFORE_RE.search(raw[max(0, m.start() - 30): m.start()]):
                return True
    return False


def detect_signals(text: str) -> dict:
    """Mirrors index.html's detectSignals() exactly (100+ signal dimensions as of the
    expansion pass — see KICKOFF_BRIEF.md Section 0)."""
    raw = text.lower()
    t = strip_negations(text).lower()

    def has(words):
        return any(w in t for w in words)

    def has_raw(words):
        return any(w in raw for w in words)

    strong_on_prem = has_raw(
        [
            "air-gapped", "air gapped", "airgapped", "cannot use any public cloud",
            # index.html has these six and this port did not, so "we run our own servers
            # in-house and cannot move to cloud" was on-prem in the browser and NOT on-prem here —
            # one missing signal cascading into nine wrong picks, including recommending AWS to an
            # air-gapped customer. Logged as an open item in PRD Section 12 until now.
            "own server", "own servers", "in-house server", "in-house servers",
            "in house server", "in house servers",
            "no public cloud", "private cloud only", "bare metal deployment",
        ]
    )
    # Unambiguous dedicated-link/hybrid-transit terms — mirrors the same fix in index.html's
    # detectSignals(): a sentence like "Direct Connect to bridge our on-prem systems to AWS" is
    # real hybrid intent, not an air-gapped requirement, even though it never says "hybrid" and
    # "cloud" together (it names the vendor directly instead).
    dedicated_link_terms = has_raw([
        "direct connect", "expressroute", "express route", "cloud interconnect",
        "dedicated link", "private link to cloud", "colocation cross-connect",
        "cross-connect", "bgp peering", "transit gateway", "virtual wan", "enterprise router",
    ])
    soft_on_prem = _mentions_on_prem_unnegated(raw) and not (
        dedicated_link_terms or (has_raw(["hybrid"]) and has_raw(["cloud"]))
    )
    hybrid_connectivity = dedicated_link_terms or (
        has_raw(["hybrid"]) and has_raw(["cloud"]) and not strong_on_prem
    )
    # Two or more DISTINCT cloud providers named — mirrors index.html's multiCloudMentioned.
    # Counts vendor groups, not raw keyword hits, and reuses the exact same keyword sets as
    # awsShop/azureShop/gcpShop/huaweiShop below for consistency.
    cloud_vendor_count = sum([
        has(["aws", "amazon web services"]), has(["azure", "microsoft"]),
        has(["gcp", "google cloud"]), has(["huawei", "huawei cloud"]),
    ])
    multi_cloud_mentioned = cloud_vendor_count >= 2

    _exclusions = detect_exclusions(text)
    return {
        "onPrem": strong_on_prem or soft_on_prem,
        "hybridConnectivity": hybrid_connectivity,
        "multiCloudMentioned": multi_cloud_mentioned,
        # Objects, not booleans — any consumer counting "active signals" must skip these.
        "excluded": _exclusions,
        # Sorted list, not the raw set detect_excluded_language_terms() works with internally —
        # this signals dict crosses a real JSON boundary (the /api/recommend router and the MCP
        # tool both serialize it), and a bare Python set isn't JSON-serializable.
        "excludedLanguageTerms": sorted(detect_excluded_language_terms(text)),
        "known": detect_known_tech(text, _exclusions),
        "latencyTarget": detect_latency_target(text),
        "concurrencyTarget": detect_concurrency_target(text),
        "timeline": detect_timeline(text),
        "brownfieldOmnichannel": has([
            "omnichannel ai support", "omnichannel support", "omni-channel ai",
            "multiple channels", "across channels", "web widget, whatsapp", "channel routing",
        ]),
        "healthcare": has(["health", "hipaa", "patient", "clinical", "ehr", "medical"]),
        "finance": has(["fintech", "bank", "payment", "fraud", "pci", "transaction", "trading", "ledger", "finance"]),
        "ecommerce": has(["ecommerce", "e-commerce", "retail", "shopping", "product recommendation", "cart", "checkout"]),
        "enterprise": has(["enterprise", "large organization", "corporate", "multi-region", "audit logging", "role-based access", "okta", "sso"]),
        "startupMvp": has(["startup", "mvp", "early-stage", "small team", "move fast", "budget conscious", "budget-conscious", "bootstrapped"]),
        # Distinct from startupMvp: a startup still intends to acquire real users and may need to
        # scale. A minimal/learning project explicitly does not — mirrors index.html's minimalProject.
        "minimalProject": has([
            "college project", "university project", "school project", "student project",
            "personal project", "hobby project", "learning project", "side project",
            "portfolio project", "coursework", "capstone", "final year project",
            "class assignment", "course assignment", "toy project", "practice project",
            "just for learning", "just to learn", "proof of concept", "weekend project",
            "solo project", "learning exercise",
        ]),
        "highScale": has(["high traffic", "high volume", "high transaction", "scale", "millions of users", "peak load", "sales event", "black friday"]),
        "realtime": has(["real-time", "real time", "low latency", "streaming", "live"]),
        "chatbot": has(["chatbot", "conversational", "customer support bot", "assistant", "virtual agent"]),
        "knowledgeBase": has(["knowledge base", "internal documents", "policy documents", "confluence", "wiki", "document search", "faq"]),
        "agentic": has(["agentic", "multi-agent", "take actions", "automate workflow", "autonomous", "tool use", "function calling"]),
        "mobile": has(["mobile", "flutter", "ios", "android", "react native"]),
        "web": has(["web app", "website", "web application", "react", "angular", "vue"]),
        # Domain floors (docs/manual-qa-test-matrix.csv TC-05/06/07/09) — mirrors index.html
        # exactly (same keyword lists). See that file's comment for the full rationale.
        "browserExtension": has(["chrome extension", "browser extension", "firefox extension", "safari extension", "edge extension", "manifest v3", "browser add-on", "browser addon"]),
        "cliTool": has(["command line tool", "command-line tool", "cli tool", "cli utility", "command line application", "command-line application", "terminal application", "terminal tool", "console application"]),
        "desktopApp": has(["desktop application", "desktop app", "cross-platform desktop", "electron app", "tauri app", "native desktop", "desktop software"]),
        # The second half MUST use has_raw(), not has(): "no backend" is itself a negation
        # phrase, so strip_negations() already deleted it from `t` by this point — same
        # reasoning as strong_on_prem's has_raw(...) elsewhere in this function.
        "staticSite": has(["static site", "static website", "static web site", "marketing website", "landing page", "brochure site", "jamstack"])
        and has_raw(["no backend", "no back-end", "no back end", "no server-side", "no server side", "no dynamic content", "purely static", "static hosting only", "without a backend", "without a back-end"]),
        "voice": has(["voice", "speech", "call center", "ivr"]),
        "compliance": has(["soc2", "hipaa", "pci", "gdpr", "compliance", "regulated", "audit"]),
        "security": has(["security", "pii", "sensitive data", "encryption", "zero trust"]),
        "dataHeavy": has(["big data", "analytics", "data pipeline", "data lake", "etl", "warehouse"]),
        "structured": has(["structured data", "relational", "transactional", "sql", "ledger", "orders"]),
        "unstructured": has(["unstructured", "documents", "pdf", "images", "logs", "text data"]),
        "iot": has(["iot", "sensor", "device telemetry", "edge device"]),
        "tablet": has(["tablet", "ipad"]),
        "liveMultiplayer": has(["leaderboard", "multiplayer", "game room", "live quiz", "trivia", "live poll", "live voting", "live session", "concurrent players", "battle royale", "live game", "live scoring"]),
        "fixedScope": has(["fixed-price", "fixed price", "fixed-scope", "fixed scope", "contractual delivery", "waterfall", "gated delivery", "fixed-bid", "government contract", "defense contract", "rfp", "statement of work"]),
        "togafMentioned": has(["togaf"]),
        "safeMentioned": has(["scaled agile", "safe framework", "safe (scaled agile)"]),
        "cobitMentioned": has(["cobit"]),
        "itilMentioned": has(["itil"]),
        "mtlsMentioned": has(["mtls", "mutual tls", "spiffe", "spire", "workload identity", "zero trust", "zero-trust"]),
        "feedFanout": has(["news feed", "social feed", "fan out", "fan-out", "fanout", "followers", "timeline", "activity feed"]),
        "geospatial": has(["location tracking", "geolocation", "geo-location", "geospatial", "nearby drivers", "nearby", "gps", "driver location", "delivery tracking", "fleet tracking", "live map", "route optimization", "vehicle tracking", "asset tracking", "last-mile delivery", "fleet management"]),
        "collabEditing": has(["collaborative editing", "real-time collaboration", "multiplayer document", "concurrent editing", "shared whiteboard", "real-time cursors", "live cursors", "co-editing", "simultaneous editing", "crdt", "operational transformation", "google-docs-like", "google docs like", "figma-like", "figma like", "notion-like", "notion like", "sync engine", "multi-user document", "shared canvas"]),
        "videoConferencing": has(["video call", "video conferencing", "video chat", "voice chat", "voice channel", "screen sharing", "screen share", "webinar", "live video", "virtual meeting", "group call", "webrtc", "audio conferencing", "multi-party call", "virtual event", "video consultation", "video consultations", "virtual consultation", "telehealth", "telemedicine", "video appointment", "virtual visit", "video visit"]),
        "microFrontend": has(["micro-frontend", "microfrontend", "micro frontend", "module federation", "single-spa", "shell app", "multiple frontend apps", "independent team deployment", "independently deployable ui"]),
        "sagaWorkflow": has(["saga", "distributed transaction", "compensating transaction", "order processing", "order fulfillment", "checkout", "multi-step workflow across services", "eventual consistency", "workflow engine", "temporal workflow", "step functions"]),
        "multiTenant": has(["multi-tenant", "multitenant", "multi-tenancy", "white-label", "white label", "per-customer data isolation", "tenant isolation", "saas for multiple companies", "saas for multiple organizations", "b2b saas platform"]),
        "marketplace": has(["marketplace", "two-sided platform", "buyers and sellers", "gig platform", "booking platform", "on-demand platform", "escrow", "split payment", "seller onboarding", "host/guest", "driver/rider", "multi-vendor"]),
        "mlFeatureStore": has(["recommendation model", "recommender system", "fraud scoring", "fraud detection model", "risk scoring model", "ranking model", "forecasting model", "demand forecasting", "churn model", "propensity model", "custom ml model", "feature store", "model training pipeline", "model registry"]),
        "searchRecommendation": has(["search bar", "product search", "site search", "search relevance", "autocomplete", "instant search", "faceted search", "recommendations", "recommended for you", "you may also like", "personalized feed", "for you page", "discovery feed", "similar items", "related products"]),
        "routingGuardrailService": has(["route between models", "multiple llm providers", "cost-optimize llm calls", "model selection per task", "different models per task", "llm gateway", "llm proxy", "ai gateway", "centralized guardrails", "prompt injection", "jailbreak", "pii redaction", "content policy enforcement", "semantic router", "model router", "fall back to a stronger model"]),
        "selfHostInfra": has(["docker", "kubernetes", "k8s", "self-hosted", "self hosted", "own gpu", "own gpus", "own servers", "own infrastructure", "own hardware", "on our own hardware", "ollama"]),
        "awsShop": has(["aws", "amazon web services"]),
        "azureShop": has(["azure", "microsoft"]),
        "gcpShop": has(["gcp", "google cloud"]),
        "huaweiShop": has(["huawei", "huawei cloud"]),
        "oktaMentioned": has(["okta"]),
        "entraMentioned": has(["entra id", "entra", "azure ad", "azure active directory"]),
        "pingMentioned": has(["ping identity", "pingone", "ping federate"]),
        "forgerockMentioned": has(["forgerock"]),
        "oneloginMentioned": has(["onelogin", "one identity"]),
        "jumpcloudMentioned": has(["jumpcloud"]),
        "cyberarkMentioned": has(["cyberark"]),
        "sailpointMentioned": has(["sailpoint"]),
        "oracleIamMentioned": has(["oracle identity", "oracle iam", "oracle access manager"]),
        "saviyntMentioned": has(["saviynt"]),
        "clerkMentioned": has(["clerk"]),
        "workosMentioned": has(["workos", "work os"]),
        "privilegedAccess": has(["privileged access", "pam ", "vaulting", "session recording", "admin credential", "privileged account"]),
        "identityGovernance": has(["identity governance", "access certification", "access review", "segregation of duties", "sod ", "iga "]),
        "deviceMgmt": has(["device management", "mdm", "mac-heavy", "mostly macs", "byod", "endpoint management"]),
        "javaMentioned": bool(re.search(r"\bjava\b(?!script)", t, re.IGNORECASE)),
        "pythonMentioned": has(["python"]),
        "goMentioned": (
            has(["golang"])
            or bool(re.search(r"\bgo\s*(lang|language)\b", t))
            or bool(re.search(r"\b(written in|using|in)\s+go\b", t))
        ),
        "nodeMentioned": has(["node.js", "nodejs", "node js"]),
        "dotnetMentioned": has([".net", "dotnet", "asp.net", "c#"]),
        "rubyMentioned": has(["ruby on rails", "ruby/rails", "rails app"]) or bool(re.search(r"\bruby\b", t)),
        "phpMentioned": has(["php", "laravel", "symfony framework"]),
        "postgresMentioned": has(["postgres", "postgresql"]),
        "mongoMentioned": has(["mongo", "mongodb"]),
        "mysqlMentioned": has(["mysql"]),
        "oracleDbMentioned": has(["oracle database", "oracle db", "oracle sql"]),
        "sqlServerMentioned": has(["sql server", "mssql", "microsoft sql server"]),
        "reactMentioned": bool(re.search(r"\breact\b", t)) and not has(["reaction", "reactive"]),
        "angularMentioned": has(["angular"]),
        "vueMentioned": has(["vue.js", "vuejs"]) or bool(re.search(r"\bvue\b", t)),
        "vanillaWebMentioned": has(["html5", "html/css", "vanilla javascript", "vanilla js"]) or (has(["html"]) and has(["css"])),
        "dockerMentioned": has(["docker"]),
        "kubernetesMentioned": has(["kubernetes", "k8s"]),
        # Per-standard compliance flags — the generic `compliance` signal can't say WHICH regime.
        "soc2Mentioned": has(["soc2", "soc 2"]),
        "hipaaMentioned": has(["hipaa"]),
        "pciMentioned": has(["pci", "pci dss", "pci-dss"]),
        "govMentioned": has(["fedramp", "government", "defense", "public sector", "gov cloud", "govcloud"]),
        "gdprMentioned": has(["gdpr"]),
        "llmProviderMentioned": has(["anthropic", "claude", "openai", "gpt-4", "gpt4", "chatgpt",
                                     "gemini", "llama", "mistral", "deepseek", "bedrock",
                                     "azure openai", "vertex ai"]),
        "redisMentioned": has(["redis", "memcached", "valkey"]),
        "kafkaMentioned": has(["kafka", "rabbitmq", "message queue", "event bus"]),
        "microservicesMentioned": has(["microservice", "microservices"]),
        "monolithMentioned": has(["monolith", "modular monolith", "single deployable"]),
        "serverlessMentioned": has(["serverless", "lambda", "cloud functions"]),
        "openshiftMentioned": has(["openshift"]),
        "pineconeMentioned": has(["pinecone"]),
        "weaviateMentioned": has(["weaviate"]),
        "qdrantMentioned": has(["qdrant"]),
        "terraformMentioned": has(["terraform"]),
        "githubActionsMentioned": has(["github actions"]),
        "jenkinsMentioned": has(["jenkins"]),
        "gitlabCiMentioned": has(["gitlab ci", "gitlab-ci", "gitlab pipelines"]),
        "circleciMentioned": has(["circleci", "circle ci"]),
        "azureDevopsMentioned": has(["azure devops", "azure pipelines"]),
        "datadogMentioned": has(["datadog"]),
        "prometheusMentioned": has(["prometheus"]) or (has(["grafana"]) and not has(["datadog"])),
        "grafanaMentioned": has(["grafana"]),
        "splunkMentioned": has(["splunk"]),
        "dynatraceMentioned": has(["dynatrace"]),
        "newrelicMentioned": has(["new relic", "newrelic"]),
        "elkMentioned": has(["elk stack", "elasticsearch", "opensearch"]),
        "sonarqubeMentioned": has(["sonarqube", "sonar", "sonarcloud"]),
        "jprofilerMentioned": has(["jprofiler"]),
        "visualvmMentioned": has(["visualvm"]),
        "smallTeam": (
            has(["small team", "2 engineers", "3 engineers", "4 engineers", "5 engineers", "6 engineers", "solo founder", "few engineers"])
            or bool(re.search(r"\b([1-9]|1[0-2])[- ]?(person|people)\b", t))
            or bool(re.search(r"team of\s*([1-9]|1[0-2])\b", t))
        ),
        "largeTeam": has(["large team", "many teams", "multiple teams", "platform team"]),
        "globalMultiRegion": has(["global", "multi-region", "worldwide", "international"]),
        "search": has(["search engine", "semantic search", "recommendation"]),
        "email": has(["email drafting", "email assistant", "draft email"]),
        "ragNeed": has(["knowledge base", "document search", "internal documents", "confluence", "faq", "clinical knowledge", "policy documents", "search across"]),
    }


# ---------- Category logic ----------


def pick_cloud(s):
    if s["onPrem"]:
        return {"v": "On-premises / private infrastructure — no public cloud", "why": "An air-gapped or explicit no-public-cloud requirement rules out AWS/Azure/GCP entirely. You need a private data center, bare-metal, or air-gapped virtualization stack (VMware, OpenStack, or a vetted sovereign/government enclave) instead.", "conf": "high"}
    if s["awsShop"]:
        return {"v": "AWS", "why": "Explicit AWS usage detected — build on existing footprint (IAM, VPC, billing) rather than introducing a second cloud.", "conf": "high"}
    if s["huaweiShop"]:
        return {"v": "Huawei Cloud", "why": "Explicit Huawei Cloud usage detected — build on existing footprint rather than introducing a second cloud, particularly relevant for APAC/China-market deployments or markets where Huawei is an approved vendor under local data-residency rules.", "conf": "high"}
    if s["gcpShop"] or s["agentic"]:
        return {"v": "Google Cloud (GCP)", "why": "GCP mentioned, or agentic/data-heavy workload — GCP pairs well with Vertex AI, BigQuery, and Gemini models.", "conf": "high" if s["gcpShop"] else "medium"}
    if s["azureShop"] or s["enterprise"]:
        return {"v": "Microsoft Azure", "why": "Azure mentioned, or enterprise context with likely existing Microsoft 365/AD investment.", "conf": "high" if s["azureShop"] else "medium"}
    if s["minimalProject"] and not s["highScale"] and not s["compliance"] and not s["finance"] and not s["healthcare"]:
        return {"v": "No cloud provider needed — deploy to a free-tier PaaS (Vercel/Netlify/Render/Railway/Fly.io) or run it locally", "why": "Nothing about this project needs a cloud ACCOUNT, let alone a specific provider — that's infrastructure for handling scale, uptime SLAs, and multi-region traffic, none of which a learning/personal project has. A free-tier PaaS deploy gives you a public URL to share with zero cloud-provider setup, IAM, or billing account. Introduce AWS/Azure/GCP only if you outgrow the PaaS's free tier or need a managed service (e.g. a specific ML API) the PaaS doesn't offer.", "conf": "high"}
    if s["startupMvp"]:
        return {"v": "AWS (or GCP)", "why": "Broadest managed-service catalog and hiring pool for a small team moving fast; GCP is a fine alternative if the team is more data/ML-leaning.", "conf": "medium"}
    return {"v": "AWS", "why": "Default choice given broadest ecosystem maturity; revisit if there is an existing cloud commitment.", "conf": "low"}


def pick_gateway(s):
    if s["onPrem"]:
        return {"v": "Internal API gateway (Kong or Apigee Edge on-prem, or NGINX/Envoy) — no public CDN/edge service", "why": "Cloudflare and similar public edge services require internet egress, which an air-gapped environment doesn't have. Run your gateway entirely inside the isolated network boundary.", "conf": "high"}
    if s["huaweiShop"]:
        return {"v": "Huawei Cloud APIG (API Gateway) + ROMA Connect for integration/eventing", "why": "Explicit Huawei Cloud usage detected — APIG is Huawei's native API gateway; ROMA Connect adds enterprise integration (ESB-style) and eventing on top if you need to bridge multiple backend services.", "conf": "high"}
    picks = []
    hits = 0
    if s["security"] or s["compliance"] or s["highScale"]:
        picks.append("Cloudflare (WAF, DDoS, edge caching, bot management)")
        hits += 1
    if s["enterprise"] or s["largeTeam"]:
        picks.append("Apigee (API lifecycle management, monetization, enterprise governance)")
        hits += 1
    if not picks:
        picks.append("Cloud-native gateway (AWS API Gateway / GCP API Gateway) + Cloudflare in front for DNS & DDoS protection")
    return {"v": " + ".join(picks), "why": "Cloudflare handles edge security/performance; Apigee (if present) adds API productization and governance for many external consumers.", "conf": "high" if hits >= 2 else "medium" if hits == 1 else "low"}


IAM_VENDORS = [
    {"id": "okta", "name": "Okta", "cat": "SSO / IdP", "bestFor": "General default — broadest app-integration catalog, no strong ecosystem pull elsewhere", "strength": "Largest pre-built app/SSO integration library; mature admin & developer APIs", "drawback": "2025–26 repricing bundled SSO+MFA with a ~$1,500/yr minimum, raising the entry bar for very small teams; per-seat cost scales quickly; governance (OIG) is a costly add-on with less delta-review depth than purpose-built IGA tools", "pricing": "~$6/user/mo (Starter, SSO+MFA) · ~$17/user/mo (Enterprise/Essentials) · Auth0 (CIAM) from ~$3,000/mo enterprise"},
    {"id": "entra", "name": "Microsoft Entra ID", "cat": "SSO / IdP", "bestFor": "Organizations already on Microsoft 365 / Azure AD", "strength": "Bundled into M365 E3/E5 — often close to free marginal cost; native Azure/Windows/Intune integration", "drawback": "Governance feels bolted-on rather than purpose-built; advanced conditional access needs the pricier P2 tier; weaker for non-Microsoft SaaS sprawl and non-human identity coverage", "pricing": "Free tier w/ M365 · P1 ~$6/user/mo · P2 ~$9/user/mo · Governance add-on ~$7/user/mo"},
    {"id": "ping", "name": "Ping Identity (incl. ForgeRock, post-merger)", "cat": "SSO / IdP", "bestFor": "Large enterprises with hybrid/on-prem infrastructure or complex legacy federation", "strength": "Strong federation & hybrid deployment flexibility; ForgeRock's customization depth is being folded in", "drawback": "Complex modular architecture needs dedicated engineers; longer implementations; product roadmap still consolidating post-merger (as of 2026); Thoma Bravo also owns SailPoint — don't assume Ping-vs-SailPoint is neutral competitive shopping", "pricing": "PingOne Workforce from ~$3/user/mo (5,000-seat minimum) · Plus ~$6/user/mo · enterprise bundles custom-quoted"},
    {"id": "onelogin", "name": "OneLogin (One Identity)", "cat": "SSO / IdP", "bestFor": "Cost-sensitive mid-market teams that want Okta-like SSO for less", "strength": "Materially cheaper than Okta for comparable core SSO/provisioning; accessible admin UI; published pricing", "drawback": "Thinner integration library than Okta; minimal governance/access-review features; some reported service-interruption/support-responsiveness issues; roadmap has slowed since the One Identity acquisition", "pricing": "~$3–10/user/mo · Enterprise custom-quoted"},
    {"id": "jumpcloud", "name": "JumpCloud", "cat": "SSO / IdP + Device Mgmt", "bestFor": "Small-to-mid-market teams (up to ~1,000 employees) that also need device/MDM management, especially Mac-heavy fleets", "strength": "Unifies SSO + directory + device management in one console — avoids stacking a separate MDM tool", "drawback": "Thinner governance/access-review capability; not built for enterprise-scale compliance needs", "pricing": "Free tier (small orgs) · Device mgmt from ~$9/user/mo · SSO/directory ~$13/user/mo · Platform bundle ~$19/user/mo"},
    {"id": "oracle", "name": "Oracle IAM (Access/Identity Manager)", "cat": "SSO / IdP + Governance", "bestFor": "Organizations already running Oracle Cloud/on-prem infrastructure", "strength": "Dual SaaS + on-prem deployment options; broad legacy-resource support (agent-based); fits naturally into an existing Oracle estate", "drawback": "Interface complexity and reported performance issues; strongest value is concentrated in Oracle-centric shops, less compelling otherwise", "pricing": "Custom tiered pricing, starting ~$3/user/mo (Workforce Users)"},
    {"id": "cyberark", "name": "CyberArk", "cat": "PAM (not an IdP)", "bestFor": "Regulated enterprises (finserv/healthcare/gov) needing to secure privileged/admin credentials specifically", "strength": "Mature credential vaulting, session recording, and SIEM/SOAR integration for privileged accounts; machine-identity management via Venafi", "drawback": "PAM-first design makes it heavy for ordinary workforce SSO; governance layer (Zilla) still maturing; real implementation needs professional services (often 20–40% of first-year license cost on top)", "pricing": "Reported median ~$31k/yr for a base deployment; full multi-module rollouts commonly reach seven figures over 3 years"},
    {"id": "sailpoint", "name": "SailPoint", "cat": "IGA (not an IdP)", "bestFor": "Large regulated enterprises that need formal access certification / segregation-of-duties workflows for audit", "strength": "Deepest IGA feature set in the category (reported ~53% of Fortune 500 use it); mature SoD enforcement and audit-trail reporting for SOX/GDPR/HIPAA-style compliance programs", "drawback": "12–24 month implementations; static role model with quarterly (not delta) reviews; implementation services often add 30–60% on top of first-year license; commonly oversized for mid-market", "pricing": "Reported median ~$111k/yr plus substantial implementation services"},
    {"id": "saviynt", "name": "Saviynt", "cat": "IGA + PAM (not an IdP)", "bestFor": "Cloud-forward enterprises wanting one converged platform instead of separate IGA + PAM tools", "strength": "Cloud-native architecture; strong AWS/Azure/GCP/Snowflake coverage; converges IGA, PAM, and application governance in one platform; covers human, non-human, and AI-agent identities", "drawback": "Steep learning curve and UI friction reported; still needs professional services for most real deployments; pricing reflects enterprise positioning", "pricing": "Custom, demo-led pricing — typically low-to-mid six figures/yr plus services"},
    {"id": "clerk", "name": "Clerk", "cat": "CIAM / Embedded Auth (not a workforce IdP)", "bestFor": "Product teams (esp. React/Next.js) that want to ship user sign-in/sign-up/profile UI fast without building it themselves", "strength": "Prebuilt, themeable UI components for auth plus user/org management ship in hours, not weeks; built-in multi-tenant \"Organizations\" primitive for B2B apps; passkeys/social/email/SMS login out of the box", "drawback": "Billed on MRU (monthly retained users, not raw signups) but overage still adds up well before enterprise scale; deepest DX is React/Next.js-first — other stacks integrate via API/SDK with less polish; this is app-user auth, not a workforce IdP — don't confuse it with the Okta/Entra rows above", "pricing": "Free up to 50,000 MRU/app · Pro $25/mo (+$0.02/MRU 50k–100k tapering to $0.012/MRU past 10M) · Business $300/mo · Enterprise custom"},
    {"id": "workos", "name": "WorkOS", "cat": "CIAM / Embedded Auth (not a workforce IdP)", "bestFor": "B2B SaaS that needs to sell \"we support enterprise SSO/SCIM\" to upmarket customers without building SAML/OIDC federation in-house", "strength": "Fastest path to checking the enterprise-readiness box (SSO, Directory Sync/SCIM, audit logs, admin portal) that enterprise security reviews commonly require; AuthKit bundles full end-user auth (password, social, passkeys, MFA, magic link) on the same free tier", "drawback": "SSO/Directory Sync is priced per IdP connection, not per user — selling to many small customers each wanting their own IdP connection gets expensive fast; this solves enterprise-SSO-as-a-feature for your own product, it isn't a workforce identity provider like Okta/Entra above", "pricing": "AuthKit: free to 1M MAU, then $2,500/mo per additional 1M · SSO/Directory Sync: $125/connection (1–15) tapering to $65/connection (51–100), custom above 100"},
]

IAM_METRICS = [
    {"m": "Orphaned account rate", "target": "Target: 0% (~1% tolerance during transitions) — active accounts with no valid owner/justification"},
    {"m": "Dormant account rate", "target": "Auto-disable at 90 days no sign-in (human accounts), 180 days (service accounts)"},
    {"m": "Time-to-deprovision", "target": "24h for standard accounts · 4h for privileged roles · same-day for high-risk departures"},
    {"m": "MFA coverage", "target": "95%+ of workforce · 100% of privileged/admin accounts"},
    {"m": "Phishing-resistant MFA adoption (passkeys/FIDO2/WebAuthn)", "target": "100% of privileged accounts · 50%+ of general workforce within one year"},
    {"m": "SSO adoption", "target": "80%+ of apps federated · 90%+ of authentications going through SSO"},
    {"m": "Access review completion & remediation", "target": "100% of certification campaigns completed on schedule · critical findings revoked within 48h"},
    {"m": "JIT privileged access coverage", "target": "90%+ of admin access granted just-in-time with approval + expiry, not standing"},
]

IAM_BEST_PRACTICES = [
    "Discover everything first — you can't govern apps, identities, and permissions you don't have a full inventory of, including shadow IT and non-human identities.",
    "Default to zero trust — verify every access request independently rather than trusting anything inside the network boundary.",
    "Enforce least privilege continuously — access should decay over time via pruning/right-sizing, not just get set once at provisioning.",
    "Phishing-resistant MFA (passkeys/hardware keys) on every privileged account — SMS and push notifications aren't sufficient there.",
    "Centralize under SSO wherever possible — it's what makes fast provisioning and, critically, fast revocation actually possible.",
    "Automate joiner-mover-leaver from HR system events, not manual tickets — this is what keeps time-to-deprovision low in practice.",
    "Replace static quarterly access reviews with continuous delta reviews — review what changed since last time, not the whole list every cycle.",
    "Just-in-time access for elevated permissions — time-bound and auto-expiring, not standing admin rights.",
    "Govern non-human identities (service accounts, API keys, tokens) with the same rigor as human accounts.",
    "AI agent access controls: scope every agent to minimal permissions, make access time-bound, log every action taken, and keep a revocation path — apply this specifically wherever this report recommends an agentic/MCP pattern.",
]


def pick_iam(s):
    if s["onPrem"]:
        primary = {"id": "selfhosted", "v": "Self-hosted open-source IdP (Keycloak or FreeIPA)", "why": "None of the mainstream SaaS identity providers (Okta, Entra ID, Ping, OneLogin, JumpCloud) can run air-gapped — they are hosted cloud services by design. A self-hosted, open-source IdP inside your network boundary is the realistic option.", "conf": "high"}
    elif s["minimalProject"] and not s["enterprise"] and not s["compliance"]:
        primary = {"id": "builtin", "v": "Your framework's built-in auth (or a lightweight library — Auth.js/NextAuth, Passport, Devise) — no IAM vendor", "why": "A dedicated identity vendor (Okta, Entra ID) solves problems a learning/personal project doesn't have: multiple client apps sharing one login, enterprise SSO/SCIM provisioning, compliance audit trails. A framework auth library gives you real login/session security (hashed passwords, secure sessions) without an external account or per-user pricing. Move to a vendor if you add a second app that needs to share login, or a customer specifically demands enterprise SSO.", "conf": "high"}
    elif s["oktaMentioned"]:
        primary = {"id": "okta", "v": "Okta", "why": "Explicit Okta usage detected — build on existing footprint rather than migrating identity providers.", "conf": "high"}
    elif s["entraMentioned"] or (s["azureShop"] and not s["gcpShop"] and not s["awsShop"]):
        primary = {"id": "entra", "v": "Microsoft Entra ID", "why": "Already-Microsoft context (Azure/M365) makes Entra ID close to a marginal-cost decision — you're likely paying for at least P1-equivalent licensing already, and it integrates natively with the rest of the Microsoft stack.", "conf": "high" if s["entraMentioned"] else "medium"}
    elif s["pingMentioned"] or s["forgerockMentioned"]:
        primary = {"id": "ping", "v": "Ping Identity (incl. ForgeRock, post-merger)", "why": "Explicit Ping/ForgeRock mention detected. Note the two companies merged in 2023 and are still consolidating product roadmaps as of 2026 — validate current packaging before committing budget.", "conf": "high"}
    elif s["oracleIamMentioned"]:
        primary = {"id": "oracle", "v": "Oracle IAM (Access/Identity Manager)", "why": "Explicit Oracle IAM mention detected — likely reflects an existing Oracle Cloud/on-prem footprint, which is where this product delivers most of its value.", "conf": "high"}
    elif (s["enterprise"] or s["largeTeam"]) and (s["compliance"] or s["security"]) and not s["startupMvp"] and not s["smallTeam"]:
        primary = {"id": "ping", "v": "Ping Identity (incl. ForgeRock, post-merger) — or Okta if you want a less complex rollout", "why": "Large regulated org with likely hybrid/legacy federation needs benefits from Ping's deployment flexibility; Okta remains the simpler-to-implement enterprise default if you don't specifically need hybrid federation depth.", "conf": "medium"}
    elif s["deviceMgmt"] and (s["startupMvp"] or s["smallTeam"]):
        primary = {"id": "jumpcloud", "v": "JumpCloud", "why": "You need SSO/directory AND device management, and you're a small team — JumpCloud unifies both in one console instead of stacking a separate MDM tool, at a lower blended cost than Okta + Jamf/Intune.", "conf": "high"}
    elif s["jumpcloudMentioned"]:
        primary = {"id": "jumpcloud", "v": "JumpCloud", "why": "Explicit JumpCloud mention detected.", "conf": "high"}
    elif s["oneloginMentioned"]:
        primary = {"id": "onelogin", "v": "OneLogin (One Identity)", "why": "Explicit OneLogin mention detected.", "conf": "high"}
    elif s["clerkMentioned"]:
        primary = {"id": "clerk", "v": "Clerk", "why": "Explicit Clerk mention detected. Note this is app-user (CIAM) auth, not a workforce identity provider — if you also need employee/workforce SSO (Okta/Entra-style), that's a separate, complementary purchase, not a replacement.", "conf": "high"}
    elif s["workosMentioned"]:
        primary = {"id": "workos", "v": "WorkOS", "why": "Explicit WorkOS mention detected. Note this is app-user (CIAM) auth / enterprise-SSO-as-a-feature for your own product, not a workforce identity provider — if you also need employee/workforce SSO (Okta/Entra-style), that's a separate, complementary purchase, not a replacement.", "conf": "high"}
    elif s["startupMvp"] or (s["smallTeam"] and not s["enterprise"]):
        primary = {"id": "onelogin", "v": "OneLogin (One Identity) — or cloud-native (AWS Cognito / Firebase Auth) for the simplest cases", "why": "Materially cheaper than Okta for comparable core SSO/provisioning, which matters more than governance depth at your stage; move to Okta or Entra ID once you have enterprise/B2B SSO customers demanding it.", "conf": "medium"}
    elif s["enterprise"]:
        primary = {"id": "okta", "v": "Okta", "why": "Enterprise-grade IdP with strong SSO/SCIM support and the deepest app-integration catalog — the safe general default absent a specific reason (existing Microsoft/Ping footprint, device-mgmt need, or budget pressure) to pick an alternative.", "conf": "medium"}
    else:
        primary = {"id": "okta", "v": "Okta (or cloud-native IAM)", "why": "Use Okta once you need enterprise SSO/SCIM/compliance audit trails; otherwise a managed cloud IAM (Cognito/Firebase Auth) is sufficient.", "conf": "low"}

    complementary = []
    if s["privilegedAccess"] or (s["enterprise"] and (s["compliance"] or s["finance"]) and (s["security"] or s["healthcare"])):
        complementary.append({
            "vendor": "CyberArk", "cat": "PAM",
            "why": "Your profile involves privileged/admin credentials in a regulated context — this is a genuinely different problem from workforce SSO (protecting the accounts that can change infrastructure/data, not just logging employees in). Layer it on top of your primary IdP pick above, don't treat it as a replacement.",
            "conf": "high" if s["privilegedAccess"] else "medium",
        })
    if s["saviyntMentioned"]:
        complementary.append({
            "vendor": "Saviynt", "cat": "IGA + PAM",
            "why": "Explicit Saviynt mention detected — a cloud-native converged alternative to buying separate IGA and PAM tools, with stronger multi-cloud (AWS/Azure/GCP) coverage than SailPoint. Still layer it on top of your primary IdP pick above, not instead of it.",
            "conf": "high",
        })
    elif s["identityGovernance"] or (s["enterprise"] and s["largeTeam"] and s["compliance"]):
        ping_already = primary["id"] == "ping"
        why = (
            "Formal access-certification / segregation-of-duties workflows for audit (SOX/GDPR/HIPAA-style) are a compliance-program purchase, not a quick add-on — expect a 12–24 month implementation and a reported median around $111k/yr plus substantial services for SailPoint specifically. Only take this on if you have an actual audit/compliance mandate requiring it; it is commonly oversized for mid-market teams."
        )
        if ping_already:
            why += " Since your primary IdP pick above is Ping, note that Ping and SailPoint share the same majority owner (Thoma Bravo) — worth knowing going into vendor conversations, even though the products themselves still solve different problems."
        complementary.append({
            "vendor": "SailPoint (or Saviynt for a more modern, cloud-native converged IGA+PAM alternative)",
            "cat": "IGA", "why": why,
            "conf": "high" if s["identityGovernance"] else "medium",
        })

    result = dict(primary)
    result["primaryId"] = primary["id"]
    result["alternatives"] = IAM_VENDORS
    result["complementary"] = complementary
    return result


# =====================================================================
# Vendor/alternatives comparison data — Groups 1-4 of the alternatives research
# project (see ../docs/alternatives-research/*.md for full sourcing/pricing/audit
# notes). Same shape as IAM_VENDORS: id/name/cat/bestFor/strength/drawback/pricing.
# index.html renders these via renderAltToggle() as an inline "See alternatives"
# toggle; this backend port omits that HTML-rendering helper (and confLabelStr(),
# also pure presentation) since the MCP tool returns structured data, not HTML —
# the vendor tables and pick*Vendor() selection logic themselves are ported in
# full, since primaryId selection is real recommendation logic, not rendering.
# =====================================================================


# --- Group 1: Infra ---


def pick_cloud_vendor(cloud):
    v = cloud["v"]
    primary_id = "aws" if "AWS" in v else "azure" if "Azure" in v else "gcp" if "GCP" in v else None if "On-premises" in v else "aws"
    return {"v": cloud["v"], "why": cloud["why"], "primaryId": primary_id, "conf": cloud["conf"]}


CLOUD_VENDORS = [
    {"id": "aws", "name": "AWS", "cat": "Hyperscaler", "bestFor": "Enterprise scale, broadest managed-service catalog, regulated industries", "strength": "Deepest service breadth (ML/data/compute), largest talent pool, most third-party integrations", "drawback": "Most expensive at small-to-mid scale; steep learning curve; pricing complexity", "pricing": "Baseline for comparison — usually the priciest per category"},
    {"id": "azure", "name": "Microsoft Azure", "cat": "Hyperscaler", "bestFor": "Microsoft-shop orgs (AD/Entra, .NET, M365 integration)", "strength": "Best-in-class enterprise identity/compliance tooling, hybrid on-prem story (Arc/Stack)", "drawback": "Still hyperscaler-tier pricing overall", "pricing": "Cheaper than AWS EC2 in ~64% of tracked categories (609/948)"},
    {"id": "gcp", "name": "Google Cloud (GCP)", "cat": "Hyperscaler", "bestFor": "Data/ML-heavy workloads, Kubernetes-native teams", "strength": "Strong data/analytics stack (BigQuery), best free tier for serverless", "drawback": "Smaller enterprise support org than AWS/Azure; deprecation reputation", "pricing": "Cheaper than AWS EC2 in ~96% of tracked categories (47/49)"},
    {"id": "digitalocean", "name": "DigitalOcean", "cat": "Simplified IaaS", "bestFor": "Small teams, startups, side projects wanting predictable flat pricing", "strength": "Radically simpler UX than hyperscalers, flat droplet pricing", "drawback": "Smaller service catalog (no deep ML/data stack), fewer regions", "pricing": "Cheaper than AWS EC2 in all 15 tracked categories"},
    {"id": "hetzner", "name": "Hetzner", "cat": "Budget IaaS (EU)", "bestFor": "Cost-sensitive workloads, EU data-residency requirements", "strength": "Lowest raw compute $/vCPU in the market by a wide margin", "drawback": "EU-only data centers; thinner enterprise SLA tier", "pricing": "Cheaper than AWS EC2 in all 15 tracked categories — often the cheapest overall"},
    {"id": "oracle", "name": "Oracle Cloud (OCI)", "cat": "Hyperscaler (DB-focused)", "bestFor": "Oracle DB workloads, orgs wanting an aggressive free tier", "strength": "Strong \"Always Free\" tier, competitive high-memory/bare-metal pricing", "drawback": "Smaller ecosystem/community than the big 3", "pricing": "Cheaper than AWS EC2 in all 24 tracked categories"},
    {"id": "linode", "name": "Linode (Akamai)", "cat": "Simplified IaaS", "bestFor": "Developers wanting simple VPS + CDN (Akamai edge) combo", "strength": "Simple pricing, Akamai edge/CDN network bundled", "drawback": "Smaller platform breadth post-acquisition still settling", "pricing": "Cheaper than AWS EC2 in ~83% of tracked categories (49/59)"},
    {"id": "vultr", "name": "Vultr", "cat": "Budget IaaS", "bestFor": "High-frequency compute/GPU rental, global points-of-presence", "strength": "Wide global region footprint for a budget provider, GPU availability", "drawback": "Smaller managed-service ecosystem, support tier below hyperscalers", "pricing": "Competitive with Hetzner/DO on raw compute"},
]
CLOUD_NOTE = "DigitalOcean/Hetzner/Oracle/Linode/Vultr are not drop-in hyperscaler replacements for workloads needing deep managed-service catalogs (managed Kafka, ML platforms, broad compliance certs) — they're the better bet specifically when a small/cost-sensitive team is paying a \"hyperscaler tax\" for infrastructure that's fundamentally just VMs + block storage + a load balancer. Source: docs/alternatives-research/01-infra-cloud-compute-containers-gateway.md."

COMPUTE_VENDORS = [
    {"id": "vercel", "name": "Vercel", "cat": "PaaS (frontend)", "bestFor": "Next.js apps", "strength": "Built by the Next.js team — automatic ISR, edge middleware, image optimization", "drawback": "Hobby plan prohibits commercial use; Pro's \"Turbo\" compute runs ~9x the standard per-minute rate", "pricing": "Free (non-commercial) · $20/seat/mo Pro"},
    {"id": "netlify", "name": "Netlify", "cat": "PaaS (frontend)", "bestFor": "General frontend deployment, JAMstack", "strength": "Commercial use allowed on free tier; mature build pipeline", "drawback": "Credit-based free tier less predictable than flat limits", "pricing": "300 credits/mo free · $19/seat/mo Pro"},
    {"id": "cfpages", "name": "Cloudflare Pages", "cat": "PaaS (edge/static)", "bestFor": "Static sites, JAMstack, edge-first apps", "strength": "Unlimited bandwidth, no cold starts", "drawback": "Static/edge-function only — not a fit for stateful backend compute", "pricing": "Free, unlimited bandwidth"},
    {"id": "render", "name": "Render", "cat": "PaaS (full-stack)", "bestFor": "Backend APIs and full-stack apps needing a bundled DB", "strength": "Free tier bundles a real Postgres + Redis, not just app hosting", "drawback": "Free services spin down after 15min idle — 30-60s cold start on next request", "pricing": "Free tier · $7/mo Starter"},
    {"id": "railway", "name": "Railway", "cat": "PaaS (full-stack)", "bestFor": "Startups, Docker-based apps, teams wanting no per-seat pricing", "strength": "Usage-based (no per-seat tax), strong DX, instant deploys", "drawback": "Not a real recurring free tier — $5 one-time trial credit, then billing starts", "pricing": "$5 trial credit · $1/mo minimum"},
    {"id": "flyio", "name": "Fly.io", "cat": "PaaS (containers)", "bestFor": "Container deployments needing always-on VMs", "strength": "Always-on VMs, no cold starts, global anycast", "drawback": "No free tier for new accounts since Oct 2024 — budget it as paid-from-day-one", "pricing": "Pay-as-you-go, no free minimum"},
    {"id": "lambda", "name": "AWS Lambda", "cat": "FaaS", "bestFor": "AWS-native event-driven backends", "strength": "1M free invocations/mo, deep AWS integration", "drawback": "API Gateway exposure billed separately ($3.50/M requests) — real HTTP cost is higher than headline free tier suggests", "pricing": "1M invocations + 400K GB-sec free/mo"},
    {"id": "cloudfn", "name": "Google Cloud Functions", "cat": "FaaS", "bestFor": "GCP/Firebase-integrated projects", "strength": "2M free invocations/mo (highest of the FaaS options), HTTP triggers included free", "drawback": "200-800ms cold start", "pricing": "2M invocations free/mo"},
    {"id": "azurefn", "name": "Azure Functions", "cat": "FaaS", "bestFor": "Microsoft/.NET shops, enterprise Azure integration", "strength": "1M free invocations/mo, native Azure AD/VNet integration", "drawback": "Lowest per-function memory ceiling (1.5GB) on the Consumption tier", "pricing": "1M invocations free/mo"},
    {"id": "cfworkers", "name": "Cloudflare Workers", "cat": "FaaS (edge)", "bestFor": "Edge computing, globally distributed APIs, I/O-heavy workloads", "strength": "<5ms cold start (V8 isolates); CPU-time-only billing makes I/O-heavy workloads reportedly 10-50x cheaper than wall-clock-billed platforms", "drawback": "10ms CPU cap per invocation on free tier (30s on paid)", "pricing": "100K requests/day free"},
]


def pick_compute_platform(s, compute):
    if s["onPrem"]:
        return {"v": "N/A — self-hosted only, see Compute Model card above", "why": "Serverless/PaaS platforms are public-cloud managed services and aren't available air-gapped — this comparison doesn't apply once on-prem is a hard requirement.", "primaryId": None, "conf": "high"}
    v = compute["v"]
    if v.startswith("Kubernetes") or v.startswith("Serverless containers"):
        return {"v": v + " — see Orchestrator Options below for the container-platform vendor comparison", "why": "Your Compute Model above is container/orchestrator-tier, not a plain FaaS/PaaS pick — the vendor comparison for that decision lives in the Orchestrator Options section below, not here.", "primaryId": None, "conf": compute["conf"]}
    if s["awsShop"]:
        return {"v": "AWS Lambda", "why": "Explicit AWS usage — Lambda keeps you on your existing IAM/VPC/billing footprint rather than introducing a second platform.", "primaryId": "lambda", "conf": "high"}
    if s["gcpShop"] or s["agentic"]:
        return {"v": "Google Cloud Functions (or Cloud Run for containers)", "why": "GCP usage or agentic/data-heavy workload — stays consistent with a GCP-centric stack and has the most generous FaaS free tier of the researched options.", "primaryId": "cloudfn", "conf": "medium"}
    if s["azureShop"]:
        return {"v": "Azure Functions", "why": "Azure usage detected — native Azure AD/VNet integration keeps this consistent with the rest of a Microsoft-centric stack.", "primaryId": "azurefn", "conf": "high"}
    if s["realtime"] or s["highScale"]:
        return {"v": "Cloudflare Workers (edge) for I/O-heavy paths, cloud-native FaaS for the rest", "why": "Workers' CPU-time billing model is a genuinely different cost shape for I/O-heavy (mostly-waiting-on-a-database) workloads at real scale — worth evaluating specifically for latency-sensitive/high-volume paths.", "primaryId": "cfworkers", "conf": "medium"}
    if s["startupMvp"] and (s["web"] or not s["mobile"]):
        return {"v": "Vercel or Netlify (frontend) + Render/Railway (backend)", "why": "Fastest path to production for a small team — PaaS platforms with bundled DBs/CI need the least glue infrastructure to stand up.", "primaryId": "render", "conf": "medium"}
    return {"v": "AWS Lambda (or your cloud's native FaaS equivalent)", "why": "Reasonable platform-neutral default absent a specific cloud commitment.", "primaryId": "lambda", "conf": "low"}


COMPUTE_NOTE = "PaaS products (Vercel/Netlify/Render/Railway/Fly.io) and FaaS primitives (Lambda/Cloud Functions/Azure Functions/Workers) answer different questions — PaaS trades cost/control for less glue infrastructure to stand up, FaaS is a lower-level building block you compose yourself. Pricing here moves fast (Netlify's Apr 2026 credit-model shift, Vercel's Turbo-compute repricing, Fly.io's Oct 2024 free-tier removal, Railway's Oct 2025 trial-credit change) — treat as directional. Source: docs/alternatives-research/01-infra-cloud-compute-containers-gateway.md."

ORCHESTRATOR_VENDORS = [
    {"id": "kubernetes", "name": "Kubernetes", "cat": "Orchestrator (baseline)", "bestFor": "Teams at real multi-service scale needing the ecosystem", "strength": "Largest ecosystem, cloud-portable, industry-standard", "drawback": "High operational complexity — overkill below a certain scale", "pricing": "Free (OSS) — cost is the cluster + ops time"},
    {"id": "openshift", "name": "OpenShift (Red Hat)", "cat": "Enterprise K8s distro", "bestFor": "Regulated enterprises wanting a supported, opinionated K8s", "strength": "Built-in CI/CD and security defaults, RH support contracts", "drawback": "Heavier, more opinionated, licensing cost", "pricing": "Subscription, enterprise-tier"},
    {"id": "nomad", "name": "Nomad (HashiCorp)", "cat": "Lightweight orchestrator", "bestFor": "Simpler scheduling without full K8s surface area, mixed container + non-container workloads", "strength": "Much simpler operational model than K8s; can schedule non-container workloads too", "drawback": "Smaller ecosystem, fewer managed offerings, smaller talent pool", "pricing": "Free (OSS)"},
    {"id": "ecs", "name": "AWS ECS", "cat": "Managed orchestrator (AWS-native)", "bestFor": "AWS-committed teams wanting less operational overhead than self-managed K8s", "strength": "Deep AWS integration, simpler mental model than K8s, Fargate serverless mode", "drawback": "AWS lock-in; smaller ecosystem than K8s", "pricing": "Pay for underlying compute (EC2/Fargate)"},
    {"id": "cloudrun", "name": "Google Cloud Run", "cat": "Serverless container platform", "bestFor": "Stateless containerized services wanting zero infra management", "strength": "True serverless container model — scales to zero, pay-per-request", "drawback": "Not a general orchestrator — no stateful-workload story, GCP-only", "pricing": "Pay-per-request"},
    {"id": "rancher", "name": "Rancher (SUSE)", "cat": "K8s management layer", "bestFor": "Multi-cluster K8s management across clouds", "strength": "Strong multi-cluster/multi-cloud K8s UI and governance", "drawback": "Adds a management layer on top of K8s, not a K8s replacement", "pricing": "OSS free · enterprise support available"},
    {"id": "dockerswarm", "name": "Docker Swarm", "cat": "Lightweight orchestrator", "bestFor": "Small teams wanting native Docker-tooling orchestration", "strength": "Simplicity, native Docker CLI integration", "drawback": "Limited feature set vs K8s; declining ecosystem momentum", "pricing": "Free (OSS)"},
]


def pick_orchestrator(s, containers):
    if s["onPrem"]:
        return {"v": "Self-managed Kubernetes (Rancher/RKE2) or Nomad", "why": "Managed orchestrator offerings (ECS, Cloud Run) are public-cloud services unavailable air-gapped — a self-managed distribution inside your network boundary is the realistic option.", "primaryId": "kubernetes", "conf": "high"}
    if s["startupMvp"]:
        return {"v": "Google Cloud Run (or AWS ECS/Fargate)", "why": "Serverless container platform gives container benefits without a Kubernetes control plane to operate — right-sized for a small team.", "primaryId": "cloudrun", "conf": "medium"}
    if s["enterprise"] or s["highScale"]:
        why = "Standard for portable, scalable container orchestration once team/scale justify the operational overhead."
        if s["enterprise"] and s["compliance"]:
            why += " If you want a more opinionated, supported distribution for a regulated environment specifically, OpenShift (see comparison below) wraps Kubernetes with built-in security defaults and a support contract — same underlying orchestrator, more guardrails."
        return {"v": "Kubernetes (EKS/GKE/AKS)", "why": why, "primaryId": "kubernetes", "conf": "high"}
    return {"v": "Kubernetes (or Nomad if you want a simpler operational model)", "why": "Default absent a strong scale/team-size signal either way.", "primaryId": "kubernetes", "conf": "low"}


ORCHESTRATOR_NOTE = "Cloud Run, ECS, and standalone Docker are single-container/serverless primitives, not general orchestrators, and Rancher is a management layer FOR Kubernetes rather than a competitor to it — presenting all of these as equivalent \"Kubernetes alternatives\" would be a categorization error. Apache Mesos/Marathon was retired Oct 17, 2025 (Apache committer vote, moved to the Apache Attic) and is intentionally excluded here. Source: docs/alternatives-research/01-infra-cloud-compute-containers-gateway.md."

GATEWAY_VENDORS = [
    {"id": "kong", "name": "Kong", "cat": "Open-source / Commercial (Konnect)", "bestFor": "Microservices environments, largest plugin ecosystem", "strength": "Established ecosystem, enterprise support tier available", "drawback": "PostgreSQL-based config storage adds overhead vs etcd-based alternatives; many billing dimensions", "pricing": "OSS free · Konnect ~$105/mo/gateway service + ~$20-34/million requests (tier-dependent)"},
    {"id": "apisix", "name": "Apache APISIX", "cat": "Open-source", "bestFor": "High-performance, multi-cloud/hybrid deployments", "strength": "Sub-millisecond proxy latency (NGINX + LuaJIT + etcd)", "drawback": "Requires operational management by your team", "pricing": "Free (OSS)"},
    {"id": "tyk", "name": "Tyk", "cat": "Open-source / Commercial (Tyk Cloud)", "bestFor": "Self-hosted or managed deployments needing full flexibility", "strength": "Full deployment flexibility, consumption-based option", "drawback": "SSO/SAML restricted to higher paid tiers", "pricing": "OSS free · Professional ~$0-3,800/mo · Enterprise custom"},
    {"id": "gravitee", "name": "Gravitee", "cat": "Open-source, event-native", "bestFor": "Async/event-driven architectures (WebSockets, WebHooks, Kafka streams)", "strength": "First-class async-API support — a genuinely different strength than REST-centric gateways", "drawback": "Smaller ecosystem than Kong/Tyk; self-hosting needs JVM + MongoDB + Elasticsearch", "pricing": "Community free · Cloud per-gateway · Enterprise custom"},
    {"id": "wso2", "name": "WSO2 API Manager", "cat": "Open-source, full-lifecycle", "bestFor": "Enterprises wanting complete self-hostable governance without vendor lock-in", "strength": "End-to-end platform (gateway + dev portal + analytics + monetization), 100% OSS", "drawback": "Self-hosting operational overhead; smaller market visibility", "pricing": "Free (OSS) · Enterprise subscription"},
    {"id": "awsgw", "name": "AWS API Gateway", "cat": "Cloud-managed", "bestFor": "AWS-native deployments wanting zero-ops", "strength": "Auto-scaling, zero-ops convenience", "drawback": "Vendor lock-in; no built-in developer portal", "pricing": "HTTP APIs $1/M requests · REST APIs $3.50/M requests · 1M free/mo for 12mo"},
    {"id": "apim", "name": "Azure API Management", "cat": "Cloud-managed", "bestFor": "Microsoft/Azure ecosystems", "strength": "Native Azure integration", "drawback": "8 pricing tiers total — genuinely complex to reason about; multi-region multiplies cost", "pricing": "Consumption ~$3.50/M calls · Developer ~$36/mo · Premium v2 ~$2,800/mo/unit"},
    {"id": "apigee", "name": "Apigee (Google)", "cat": "Cloud-managed", "bestFor": "GCP-integrated enterprise API programs", "strength": "Deep GCP ecosystem integration, managed service", "drawback": "Vendor lock-in; no hybrid/multi-cloud support; hidden add-on costs", "pricing": "$20/M standard calls · environment tiers $365-3,431/mo · enterprise $8K-25K/mo"},
]


def pick_gateway_vendor(s):
    if s["onPrem"]:
        return {"v": "Kong or APISIX, self-hosted", "why": "Public API-gateway SaaS services require internet egress an air-gapped environment doesn't have — a self-hosted open-source gateway inside the boundary is the realistic option.", "primaryId": "kong", "conf": "high"}
    if s["gcpShop"]:
        return {"v": "Apigee", "why": "GCP-native context — Apigee integrates most deeply with the rest of a Google Cloud stack.", "primaryId": "apigee", "conf": "medium"}
    if s["azureShop"]:
        return {"v": "Azure API Management", "why": "Azure-native context — APIM integrates natively with the rest of the Microsoft stack.", "primaryId": "apim", "conf": "medium"}
    if s["awsShop"]:
        return {"v": "AWS API Gateway", "why": "AWS-native context — stays on existing IAM/billing footprint.", "primaryId": "awsgw", "conf": "medium"}
    if s["enterprise"] and s["largeTeam"]:
        return {"v": "Kong (or WSO2 if you want a fully self-hostable, vendor-neutral platform)", "why": "Enterprise scale with multiple consumers benefits from Kong's ecosystem and plugin depth; WSO2 is the pick if avoiding any cloud/vendor lock-in matters more than ecosystem size.", "primaryId": "kong", "conf": "medium"}
    return {"v": "Cloud-native gateway matching your primary cloud, or Kong/APISIX if you want to stay cloud-agnostic", "why": "Default absent a strong cloud or enterprise signal.", "primaryId": "kong", "conf": "low"}


GATEWAY_NOTE = "MuleSoft (not listed above) is a full iPaaS platform, not a pure API gateway, and would misrepresent its scope if presented as a like-for-like Kong/Tyk swap. This table is a dedicated-gateway-product comparison, separate from the \"API Gateway / Edge\" stack card above, which also factors in edge/WAF/DDoS needs (Cloudflare) that these products don't all address. Source: docs/alternatives-research/01-infra-cloud-compute-containers-gateway.md."


# --- Group 2: Data layer ---

DATABASE_VENDORS = [
    {"id": "postgres", "name": "PostgreSQL", "cat": "Relational (SQL)", "bestFor": "SaaS platforms, AI/ML workloads (pgvector), analytics, fintech, geospatial", "strength": "JSONB native + indexed, 300+ extension ecosystem (PostGIS/pgvector/Citus/TimescaleDB), native row-level security", "drawback": "Requires connection pooling at high concurrency; steeper learning curve than MySQL", "pricing": "Free OSS · managed from ~$0.036/hr on-demand"},
    {"id": "mysql", "name": "MySQL", "cat": "Relational (SQL)", "bestFor": "WordPress/CMS, high-read simple CRUD, legacy PHP apps", "strength": "20-30% faster on simple SELECTs, native Group Replication, universal CMS support", "drawback": "GPL licensing complicates commercial redistribution; 65,535-byte row limit; weaker JSON support than Postgres", "pricing": "GPL free or Oracle commercial · managed ~$0.034/hr"},
    {"id": "cockroachdb", "name": "CockroachDB", "cat": "Distributed SQL", "bestFor": "Startups needing horizontal scale + Postgres compatibility without re-architecting", "strength": "Postgres-wire-compatible, distributed by default, automatic failover, most generous free-tier storage (10GiB)", "drawback": "Operational complexity for teams that don't actually need distribution", "pricing": "Free tier: 10GiB storage, 50M request units/mo"},
    {"id": "mongodb", "name": "MongoDB", "cat": "Document store", "bestFor": "Flexible-schema CMS, e-commerce catalogs", "strength": "Atlas Vector Search built in, queryable encryption, time-series collections", "drawback": "Schema flexibility can become a data-integrity liability without discipline", "pricing": "Atlas managed: consumption-based"},
    {"id": "dynamodb", "name": "DynamoDB (AWS)", "cat": "Key-value / serverless", "bestFor": "Gaming leaderboards, shopping carts, AWS-native serverless apps", "strength": "Fully managed, automatic scaling, single-digit ms latency, global tables", "drawback": "AWS lock-in; limited query flexibility (no ad-hoc joins)", "pricing": "On-demand pay-per-request or provisioned capacity"},
    {"id": "cassandra", "name": "Cassandra", "cat": "Wide-column", "bestFor": "Time-series/IoT, transaction logs, high-availability multi-DC", "strength": "Linear scalability via masterless ring architecture, tunable consistency", "drawback": "Operational complexity; eventual-consistency model needs app-level awareness", "pricing": "OSS free · managed via DataStax Astra"},
    {"id": "warehouse", "name": "Cloud data warehouse (BigQuery/Snowflake/Redshift)", "cat": "Analytics/OLAP", "bestFor": "Analytics/ETL/reporting-centric workloads, not transactional apps", "strength": "Built for large scans, aggregations, BI-tool integration — Postgres/Mongo/Cassandra aren't optimized for this", "drawback": "Wrong tool for OLTP/transactional workloads", "pricing": "Usage-based (per-query or per-slot)"},
]


def pick_database_vendor(db):
    v = db["v"].lower()
    if "warehouse" in v:
        primary_id = "warehouse"
    elif "Cassandra" in db["v"]:
        primary_id = "cassandra"
    elif "MongoDB" in db["v"]:
        primary_id = "mongodb"
    else:
        primary_id = "postgres"
    return {"v": db["v"], "why": db["why"], "primaryId": primary_id, "conf": db["conf"]}


DATABASE_NOTE = "CockroachDB and DynamoDB aren't drop-in swaps for Postgres/MongoDB — CockroachDB trades operational simplicity for horizontal-scale-by-default, and DynamoDB trades query flexibility for AWS-native zero-ops. Source: docs/alternatives-research/02-data-layer-database-cache-messaging.md."

CACHE_VENDORS = [
    {"id": "redis", "name": "Redis", "cat": "Single-threaded", "bestFor": "Shared state, pub/sub, rich data structures, Lua scripting", "strength": "15+ years production-proven, massive ecosystem, richest data-type support", "drawback": "Single-threaded throughput ceiling; license moved to SSPL/RSALv2 (not OSI-approved open source)", "pricing": "Free self-hosted under SSPL/RSALv2"},
    {"id": "valkey", "name": "Valkey", "cat": "Single-threaded", "bestFor": "Drop-in Redis replacement for teams avoiding the licensing change", "strength": "BSD-3 licensed, Linux Foundation-backed, performance parity with Redis", "drawback": "Fewer bundled modules than Redis Stack; younger community", "pricing": "Free, BSD-3"},
    {"id": "dragonfly", "name": "DragonflyDB", "cat": "Multi-threaded", "bestFor": "Maximum single-node throughput, Redis-protocol-compatible workloads", "strength": "Reports 1-4M ops/sec (3-25x Redis) via shared-nothing multi-threaded architecture", "drawback": "Smaller community; BSL 1.1 license is source-available, not fully open source", "pricing": "Free self-hosted under BSL 1.1"},
    {"id": "keydb", "name": "KeyDB", "cat": "Multi-threaded", "bestFor": "Multi-threaded Redis with active-active replication", "strength": "Active replication support, 300K-1M ops/sec", "drawback": "Smaller community; slower development pace than Redis", "pricing": "Free, BSD-3"},
    {"id": "memcached", "name": "Memcached", "cat": "Multi-threaded", "bestFor": "Simple key-value caching, session stores, lowest protocol overhead", "strength": "Simplest protocol, lowest per-key overhead", "drawback": "No data structures beyond strings, no persistence, no pub/sub/scripting", "pricing": "Free, BSD"},
]
CACHE_NOTE = "Redis' SSPL/RSALv2 license is a compliance-relevant fact, not just technical — orgs with strict open-source-license policies may need to route to Valkey/KeyDB/Memcached (permissive BSD-3) instead. Source: docs/alternatives-research/02-data-layer-database-cache-messaging.md."

MESSAGING_VENDORS = [
    {"id": "kafka", "name": "Kafka", "cat": "Distributed event log", "bestFor": "Ordered event streams needing replay", "strength": "Per-partition ordering, offset-based replay, 1M+ msgs/sec, rich ecosystem (Connect, Schema Registry)", "drawback": "Operationally heavy; overkill for simple task queues", "pricing": "Self-hosted ~$1,500-5,000/mo (3-node) or Confluent Cloud"},
    {"id": "rabbitmq", "name": "RabbitMQ", "cat": "AMQP broker, flexible routing", "bestFor": "Task queues with competing consumers; complex routing patterns", "strength": "Purpose-built for many-workers-pulling-from-one-queue; lower p99 latency (1-50ms) than Kafka", "drawback": "No replay — messages gone after consumption; per-queue-only ordering", "pricing": "Self-hosted ~$500-1,500/mo (3-node)"},
    {"id": "nats", "name": "NATS (Core + JetStream)", "cat": "Lightweight pub/sub", "bestFor": "Service-to-service RPC, lightweight multi-tenant streaming", "strength": "Sub-millisecond latency, built-in request-reply, cheap per-tenant streams (good SaaS fit)", "drawback": "Core NATS has no persistence; JetStream throughput trails Kafka", "pricing": "Self-hosted ~$300-800/mo (3-node) — cheapest researched option"},
    {"id": "sqs", "name": "Amazon SQS", "cat": "Managed queue (AWS-native)", "bestFor": "Fire-and-forget task queues inside AWS, zero-ops teams", "strength": "Fully managed, automatic scaling, high-throughput FIFO up to 70K msg/sec", "drawback": "No replay; Standard queues offer best-effort ordering only; AWS-only", "pricing": "Pay-per-request, no fixed infra cost"},
    {"id": "pubsub", "name": "Google Pub/Sub", "cat": "Managed queue (GCP-native)", "bestFor": "Fully managed, zero-ops pub/sub inside a GCP-native stack", "strength": "Native GCP integration, zero ops, at-least-once delivery guarantees", "drawback": "No event-replay/audit-trail model the way Kafka provides; GCP-only", "pricing": "Pay-per-use, no fixed infra cost"},
    {"id": "pulsar", "name": "Apache Pulsar", "cat": "Multi-region geo-replicated streaming", "bestFor": "Compliance-driven multi-region deployments, tenant-per-topic topologies", "strength": "Built-in geo-replication, independently scalable broker/storage layers", "drawback": "Smaller community than Kafka; multi-region ops needs specialized expertise", "pricing": "Self-hosted, complex; commercial support available"},
    {"id": "redpanda", "name": "Redpanda", "cat": "Kafka-wire-compatible", "bestFor": "Sub-10ms tail-latency workloads — trading, real-time fraud detection", "strength": "Drop-in Kafka client compatibility, deterministic latency via thread-per-core design", "drawback": "No Kafka Streams support; smaller ecosystem", "pricing": "Self-hosted; commercial/cloud options available"},
]


def pick_messaging_vendor(s, msg):
    v = msg["v"]
    if "Kafka" in v and "RabbitMQ" not in v:
        primary_id = "kafka"
    elif "RabbitMQ" in v:
        primary_id = "rabbitmq"
    elif "Pub/Sub" in v:
        primary_id = "pubsub"
    elif "Managed queue" in v:
        primary_id = "sqs"
    else:
        primary_id = "kafka"
    return {"v": msg["v"], "why": msg["why"], "primaryId": primary_id, "conf": msg["conf"]}


MESSAGING_NOTE = "Kafka and SQS solve genuinely different problems (ordered replayable log vs. fire-and-forget task queue) — treating one as a strict substitute for the other is a modeling error. The zero-signal default recommends RabbitMQ rather than Kafka (fixed after this research flagged the previous Kafka-first fallback as over-provisioning the generic case). Source: docs/alternatives-research/02-data-layer-database-cache-messaging.md."

# --- Group 3: AI/LLM layer ---

LLM_PROVIDER_VENDORS = [
    {"id": "openai", "name": "OpenAI", "cat": "Frontier, broadest ecosystem", "bestFor": "Deepest third-party tooling ecosystem, strongest general reasoning", "strength": "Broadest library/integration support, mature fine-tuning + batch API, input caching", "drawback": "Often highest sticker price; enterprise compliance requires routing through Azure OpenAI instead", "pricing": "Per-token, caching/batch discounts"},
    {"id": "anthropic", "name": "Anthropic Claude", "cat": "Agentic workflows, code reasoning", "bestFor": "Code assistants, multi-step agents, complex instruction-following", "strength": "Strong multi-file code understanding, production-grade computer-use, effective long-context caching", "drawback": "No public API fine-tuning; enterprise procurement often via AWS Bedrock", "pricing": "Per-token, caching at scale"},
    {"id": "gemini", "name": "Google Gemini", "cat": "Multimodal, long-context", "bestFor": "Video/audio/large-document workloads at scale", "strength": "Native 1M+ token context with multimodal input, Flash variants optimize cost/token", "drawback": "Vertex AI adds operational overhead off-GCP", "pricing": "Per-token, Flash tier for volume"},
    {"id": "azureopenai", "name": "Azure OpenAI", "cat": "Enterprise compliance wrapper", "bestFor": "Enterprises needing private networking, compliance certs, auditability", "strength": "SOC2/HIPAA/GDPR/data-residency certs, Provisioned Throughput Units for latency SLAs", "drawback": "Region-quota management overhead; throttling can occur earlier than raw OpenAI", "pricing": "Per-token + PTU"},
    {"id": "bedrock", "name": "AWS Bedrock", "cat": "Multi-model AWS-native platform", "bestFor": "AWS-committed teams wanting one API across model families", "strength": "Unified interface across Claude/Llama/Mistral/Titan, deep IAM/CloudWatch/VPC integration", "drawback": "Model availability varies by region", "pricing": "Per-token + provisioned capacity"},
    {"id": "mistral", "name": "Mistral AI", "cat": "Cost-efficient, EU-friendly, open-weight path", "bestFor": "Cost efficiency, multilingual strength, an eventual self-hosting exit ramp", "strength": "Competitive per-token pricing, open-weight models reduce lock-in, Codestral for code", "drawback": "Less mature reasoning/agentic feature set than frontier labs", "pricing": "Per-token, competitive"},
    {"id": "deepseek", "name": "DeepSeek", "cat": "Ultra-low-cost, high-volume", "bestFor": "Price-sensitive, high-volume workloads", "strength": "Reported 5-10x cheaper than frontier alternatives, OpenAI-API-compatible (easy swap-in)", "drawback": "Limited enterprise certifications; more variable reasoning consistency", "pricing": "Lowest per-token tier researched"},
    {"id": "selfhosted", "name": "Self-hosted open-weight (Llama, Mistral)", "cat": "Self-hosted", "bestFor": "Data-residency-strict requirements, or genuinely sustained high-volume/high-utilization usage", "strength": "No per-token vendor cost at scale, full data control, predictable latency", "drawback": "Break-even is steep: 160M-256M tokens/mo just to beat frontier API pricing; GPU cost multiplies fast below ~60% utilization", "pricing": "GPU rental $1,000+/mo, realistic total cost 1.3-5x raw GPU price"},
]


def pick_llm_provider(s, llm):
    if s["compliance"] or s["enterprise"] or s["security"]:
        primary_id, conf = "anthropic", "high"
    else:
        primary_id, conf = "openai", "medium"
    v = llm[0]["name"] if llm else ("Anthropic Claude" if primary_id == "anthropic" else "OpenAI GPT")
    why = "Mirrors the AI/LLM Recommendation card above — Claude for regulated/security-sensitive contexts (strong safety & instruction-following), OpenAI for the broadest general-purpose default otherwise. See that card for the full task-by-task model mapping."
    return {"v": v, "why": why, "primaryId": primary_id, "conf": conf}


LLM_PROVIDER_NOTE = "Azure OpenAI and AWS Bedrock are compliance/procurement wrappers around the same underlying models (OpenAI's, and Claude/Llama/Mistral's respectively) — not independent model choices; ideally a compliance+cloud-shop combination would route the \"best bet\" to the wrapper rather than the raw provider. AUDIT NOTE: the best-bet logic above intentionally mirrors the AI/LLM Recommendation card's existing compliance/enterprise/security → Claude-vs-OpenAI split exactly (to avoid contradicting that card, the same fix applied elsewhere in this pass) and does not yet add that cloud-wrapper or cost-tier (DeepSeek/self-hosted) routing — Azure OpenAI/Bedrock/Mistral/DeepSeek/self-hosted are fully documented as comparison rows below but never selected as the \"best bet\" today. That's a disclosed scope gap, not a hidden one — a good next refinement, best done alongside the AI/LLM Recommendation card so the two don't diverge. Self-hosting only beats API pricing at volumes most single products never reach — see the AI/LLM Recommendation and Hosting cards for the full break-even math. Source: docs/alternatives-research/03-ai-llm-layer-models-vectordb-rag-guardrails.md."

VECTORDB_VENDORS = [
    {"id": "pgvector", "name": "pgvector", "cat": "PostgreSQL extension", "bestFor": "Teams already on Postgres with <10M vectors", "strength": "Zero additional infrastructure, full ACID compliance, vectors + relational data in one transaction", "drawback": "HNSW index build time/memory pressure grows at scale", "pricing": "Free (OSS) — cost is your existing Postgres"},
    {"id": "pinecone", "name": "Pinecone", "cat": "Fully managed SaaS", "bestFor": "Startups/enterprises prioritizing speed-to-market over cost control", "strength": "Zero-ops serverless, billions-of-vectors scale, built-in inference/reranking", "drawback": "Cost predictability issues at scale — pricing climbs steeply on higher tiers", "pricing": "Free · $20+/mo (Builder) · $50+/mo (Standard) · $500+/mo (Enterprise)"},
    {"id": "qdrant", "name": "Qdrant", "cat": "Open-source + managed", "bestFor": "Budget-conscious teams still wanting production-grade performance", "strength": "Composable search (dense + sparse + filters), Rust-native, low self-hosting cost", "drawback": "Practical ceiling around ~50M vectors", "pricing": "Free tier (1GB RAM/4GB disk); self-hosted ~$30-50/mo"},
    {"id": "weaviate", "name": "Weaviate", "cat": "Open-source + managed", "bestFor": "Apps needing hybrid search (keyword + vector) in one query", "strength": "Native BM25 + vector + metadata filtering, built-in vectorization, multi-modal", "drawback": "GraphQL API has a real learning curve; JVM runtime is resource-heavy", "pricing": "$45/mo minimum up to $400+/mo (Premium)"},
    {"id": "milvus", "name": "Milvus / Zilliz Cloud", "cat": "Open-source + managed", "bestFor": "Billion-scale datasets", "strength": "Reports up to 10x query throughput improvement, GPU acceleration, distributed querying", "drawback": "Self-hosted mode needs its own metadata store, object storage, and messaging system", "pricing": "OSS free; Zilliz managed pricing available"},
    {"id": "mongoatlas", "name": "MongoDB Atlas Vector Search", "cat": "Fully managed SaaS", "bestFor": "Full-stack apps that already have operational data in MongoDB", "strength": "Eliminates data-sprawl/sync-lag between app DB and vector store", "drawback": "Only pays off if already on MongoDB; capped at 4,096-dim embeddings", "pricing": "M0 free (512MB); Flex $0-30/mo; Dedicated ~$57+/mo"},
]


def pick_vector_db_vendor(s, vector_db):
    if not vector_db["needed"]:
        return {"v": "Not required", "why": vector_db["why"], "primaryId": None, "conf": "medium"}
    db_choice = vector_db["dbChoice"]
    if "pgvector" in db_choice:
        primary_id = "pgvector"
    elif "MongoDB" in db_choice:
        primary_id = "mongoatlas"
    else:
        primary_id = "qdrant"
    return {"v": db_choice, "why": vector_db["why"], "primaryId": primary_id, "conf": "medium"}


VECTORDB_NOTE = "pgvector and MongoDB Atlas Vector Search are \"already have this database, add vectors to it\" choices, not general-purpose vector-database picks — route to these specifically when the existing-database signal already matches, not as a first-class option alongside Pinecone/Weaviate for a from-scratch build. Source: docs/alternatives-research/03-ai-llm-layer-models-vectordb-rag-guardrails.md."

GUARDRAILS_VENDORS = [
    {"id": "nemo", "name": "NVIDIA NeMo Guardrails", "cat": "Open-source, programmable middleware", "bestFor": "Engineering teams wanting deep customization, vendor-neutral across LLM providers", "strength": "Apache 2.0 (no vendor lock-in), GPU-accelerated sub-100ms latency, Colang DSL for business logic", "drawback": "Colang DSL has a real learning curve; needs your own operational infra", "pricing": "Free (OSS)"},
    {"id": "guardrailsai", "name": "Guardrails AI", "cat": "Open-source Python framework", "bestFor": "Python teams needing strict, structured output validation", "strength": "50+ pre-built composable validators, Pydantic integration, self-hosted", "drawback": "Chained-validator configs get complex; streaming support has real limitations", "pricing": "Free (OSS)"},
    {"id": "llamaguard", "name": "Llama Guard (3, 8B)", "cat": "Open-weight safety classifier (Meta)", "bestFor": "Teams wanting a dedicated input/output safety classifier model", "strength": "De facto open-source content classifier; competitive F1 on standard benchmarks", "drawback": "Uneven recall on hate speech/obfuscated requests; high false-positive rate on benign-but-sensitive content; ~50ms p99 on A100, 500ms+ on CPU", "pricing": "Free (open weights) — but real compute cost to run"},
    {"id": "lakera", "name": "Lakera Guard", "cat": "Commercial, API-based security firewall", "bestFor": "Security teams in regulated industries focused on prompt-injection/data-leakage prevention", "strength": "Single API integration, no code changes, horizontally scalable", "drawback": "Limited built-in observability; gateway becomes a potential single point of failure", "pricing": "Not publicly listed"},
    {"id": "azurecontentsafety", "name": "Azure AI Content Safety", "cat": "Cloud-managed content moderation", "bestFor": "Azure-native teams running conversational AI / RAG", "strength": "Native Azure OpenAI integration, multi-layer coverage", "drawback": "Microsoft's own docs acknowledge accuracy limitations on context-sensitive cases", "pricing": "Not publicly listed"},
    {"id": "galileo", "name": "Galileo", "cat": "Commercial, enterprise observability + runtime protection", "bestFor": "Enterprise teams running production agents needing eval + observability + runtime protection together", "strength": "Luna-2 small models reportedly hit 0.95 F1 at 98% lower cost than GPT-4o-based checking; SaaS/VPC/on-prem deploy flexibility", "drawback": "Likely overkill/over-budget for a single-LLM-app use case", "pricing": "Not publicly listed"},
    {"id": "bedrockguardrails", "name": "AWS Bedrock Guardrails", "cat": "Cloud-managed, AWS-native", "bestFor": "AWS/Bedrock-committed teams wanting guardrails as a platform feature", "strength": "Native Bedrock integration, granular per-check pricing, word/PII-regex filters free", "drawback": "AWS-only", "pricing": "Content filters $0.15/1K text units · Sensitive-info $0.10/1K · Word filters free"},
]


def pick_guardrails_vendor(s):
    if s["enterprise"] and (s["security"] or s["compliance"]):
        return {"v": "Lakera Guard (or Galileo if you need full eval + observability, not just runtime filtering)", "why": "Regulated enterprise context favors a commercial, zero-integration-effort security layer over a DIY open-source framework.", "primaryId": "lakera", "conf": "medium"}
    if s["awsShop"]:
        return {"v": "AWS Bedrock Guardrails", "why": "AWS-native context — guardrails as a Bedrock platform feature avoids standing up a separate service.", "primaryId": "bedrockguardrails", "conf": "medium"}
    if s["azureShop"]:
        return {"v": "Azure AI Content Safety", "why": "Azure-native context — integrates directly with Azure OpenAI.", "primaryId": "azurecontentsafety", "conf": "medium"}
    if s["startupMvp"] or s["smallTeam"]:
        return {"v": "NeMo Guardrails or Guardrails AI (open-source)", "why": "No dedicated security engineering budget yet — open-source frameworks avoid recurring commercial-platform cost while covering the core input/output validation needs.", "primaryId": "nemo", "conf": "medium"}
    return {"v": "NVIDIA NeMo Guardrails", "why": "Vendor-neutral, deeply customizable default absent a strong cloud or budget signal.", "primaryId": "nemo", "conf": "low"}


GUARDRAILS_NOTE = "The open-source-framework tier (NeMo, Guardrails AI, Llama Guard) and commercial-platform tier (Lakera, Galileo, Azure Content Safety, Bedrock Guardrails) answer different build-vs-buy questions — a small team with no dedicated security engineer should route toward the commercial tier's zero-integration-effort products; a team with ML engineering capacity wanting deep customization should route toward OSS. Source: docs/alternatives-research/03-ai-llm-layer-models-vectordb-rag-guardrails.md."


# --- Group 4: DevOps + Frontend ---

CICD_VENDORS = [
    {"id": "githubactions", "name": "GitHub Actions", "cat": "SaaS CI/CD", "bestFor": "Open-source projects, teams already on GitHub", "strength": "Unlimited minutes for public repos, massive Actions marketplace, tightest GitHub integration", "drawback": "macOS runner minutes cost 10x Linux rate; self-hosted runners for private repos now bill per-minute (Mar 2026 change)", "pricing": "2,000 min/mo free (private) · $4/seat + usage overages"},
    {"id": "gitlabci", "name": "GitLab CI", "cat": "SaaS + self-hosted CI/CD", "bestFor": "Enterprise teams wanting CI/CD + full DevOps platform in one product", "strength": "Free unlimited self-hosted runner execution; bundles container registry + security scanning", "drawback": "400 shared-runner minutes exhausts fast for an active team", "pricing": "400 min/mo free (shared runners) · $29/user/mo Premium"},
    {"id": "circleci", "name": "CircleCI", "cat": "SaaS CI/CD", "bestFor": "Teams wanting the most generous hosted free allowance", "strength": "30x concurrency, flexible resource classes, test splitting included", "drawback": "macOS builds burn credits 20x faster than Linux", "pricing": "6,000 min/mo free (~30,000 credits) · $15/seat Performance"},
    {"id": "jenkins", "name": "Jenkins", "cat": "Self-hosted, fully OSS", "bestFor": "Teams wanting zero vendor lock-in and full infra control", "strength": "100% free, 1,800+ plugins, runs anywhere", "drawback": "You own server admin, security patching, plugin maintenance", "pricing": "Free (MIT) — realistic infra cost ~$20-100/mo"},
    {"id": "buildkite", "name": "Buildkite", "cat": "Hybrid hosted-control-plane/self-hosted-agent", "bestFor": "Teams with existing compute infra wanting a hybrid model", "strength": "Unlimited self-hosted agents at no software cost, built-in test analytics", "drawback": "Hosted free tier capped at 3 concurrent jobs", "pricing": "500 hosted min/mo free · $15/user/mo Teams"},
]


def pick_cicd_vendor(s, cicd):
    if s["onPrem"]:
        primary_id = "jenkins"
    elif s["enterprise"]:
        primary_id = "gitlabci"
    else:
        primary_id = "githubactions"
    return {"v": cicd["v"], "why": cicd["why"], "primaryId": primary_id, "conf": cicd["conf"]}


CICD_NOTE = "Jenkins and Buildkite's self-hosted-agent model is a fundamentally different cost shape than the SaaS-runner tools — cost trades from \"per-minute usage\" to \"infra you already run.\" Route by ops-capacity signal (has existing infra vs. wants zero infra to manage), not brand familiarity. Source: docs/alternatives-research/04-devops-frontend-cicd-observability-frameworks.md."

OBSERVABILITY_VENDORS = [
    {"id": "datadog", "name": "Datadog", "cat": "Enterprise SaaS", "bestFor": "Orgs prioritizing breadth + correlation depth across metrics/traces/logs", "strength": "One-click metric-anomaly → trace → log correlation, AI-assisted analysis, 15+ integrated sub-products", "drawback": "High cost trajectory — mid-size enterprises commonly report $500K-2M+/yr; no self-hosted option", "pricing": "Usage-based, scales with data volume"},
    {"id": "grafanastack", "name": "Grafana Stack (Prometheus/Mimir + Loki + Tempo)", "cat": "Open-source, composable", "bestFor": "Cost-sensitive teams and regulated enterprises needing data residency", "strength": "Apache 2.0, native OpenTelemetry support, composable, runs anywhere", "drawback": "Real operational overhead if self-hosted; correlation needs manual configuration", "pricing": "Free/OSS core + optional Grafana Cloud SaaS tiers"},
    {"id": "newrelic", "name": "New Relic", "cat": "Enterprise APM platform", "bestFor": "Orgs with existing APM investment or prioritizing deep application-performance monitoring", "strength": "Mature APM heritage, strong language-agent support", "drawback": "Correlation UX less polished than Datadog; enterprise deployments still commonly reach $500K+/yr", "pricing": "Per-user + per-GB ingested"},
    {"id": "honeycomb", "name": "Honeycomb", "cat": "Distributed tracing specialist", "bestFor": "Teams needing high-cardinality debugging and exploratory trace analysis", "strength": "Strongest trace-based exploratory query model researched, OpenTelemetry-native", "drawback": "Narrow scope — not a full standalone platform, typically paired with something else", "pricing": "~$130/mo starting"},
    {"id": "signoz", "name": "SigNoz", "cat": "Open-source, OTel-first", "bestFor": "Teams wanting a single OSS product covering metrics+logs+traces as a Datadog alternative", "strength": "Most OpenTelemetry-centric of the researched platforms, self-hosted or cloud", "drawback": "Smaller ecosystem than established players; younger product", "pricing": "Free (OSS) + competitive cloud pricing"},
    {"id": "splunk", "name": "Splunk", "cat": "Enterprise SIEM/log platform", "bestFor": "Heavy compliance/audit log-management needs, usually paired with a dedicated APM tool", "strength": "Deep log search/analysis and compliance-reporting maturity many APM-only tools lack", "drawback": "Log-ingestion cost scales steeply at volume; not a full APM replacement on its own — not independently sourced/priced in this research pass", "pricing": "Usage-based, ingestion-volume-driven — not sourced in this research pass"},
    {"id": "dynatrace", "name": "Dynatrace", "cat": "Enterprise APM (AI-assisted)", "bestFor": "Large, complex enterprise scale wanting automatic root-cause analysis", "strength": "Strong AI-assisted automatic root-cause analysis (Davis AI)", "drawback": "Premium enterprise pricing; steep to adopt for smaller teams — not independently sourced/priced in this research pass", "pricing": "Usage-based, enterprise-tier — not sourced in this research pass"},
]


def pick_observability_vendor(s, obs):
    v = obs["v"]
    if "Splunk" in v:
        primary_id = "splunk"
    elif "Dynatrace" in v:
        primary_id = "dynatrace"
    elif "Grafana" in v:
        primary_id = "grafanastack"
    else:
        primary_id = "datadog"
    return {"v": obs["v"], "why": obs["why"], "primaryId": primary_id, "conf": obs["conf"]}


OBSERVABILITY_NOTE = "Honeycomb and the Grafana Stack answer different questions than Datadog/New Relic — Honeycomb is a specialist meant to be paired with something else, and the Grafana Stack is a build-your-own-platform choice, not a single-vendor drop-in. Route \"small team, wants one thing that works\" to all-in-one products; \"has platform-engineering capacity, cost-sensitive, needs data residency\" to self-hosted Grafana Stack. Source: docs/alternatives-research/04-devops-frontend-cicd-observability-frameworks.md."

FRONTEND_VENDORS = [
    {"id": "react", "name": "React", "cat": "Component library", "bestFor": "Complex apps needing the largest ecosystem and talent pool", "strength": "~40% of professional developers use it regularly — largest talent pool of any option here; mature ecosystem", "drawback": "Requires assembling routing/state/UI from separate libraries — no batteries-included default", "pricing": "Free (OSS)"},
    {"id": "nextjs", "name": "Next.js", "cat": "React meta-framework", "bestFor": "Production React deployments needing SSR/SSG/full-stack in one framework", "strength": "SSR + static generation + file routing + API routes bundled; Server Components cut client JS", "drawback": "De facto default for React — worth naming explicitly since React alone doesn't include this layer", "pricing": "Free (OSS); deployable on Vercel, AWS, Railway, Render, self-hosted"},
    {"id": "vue", "name": "Vue 3", "cat": "Progressive framework", "bestFor": "Teams wanting a gentler learning curve, or incremental adoption", "strength": "Template-based syntax lowers the learning curve, genuinely progressive adoption model", "drawback": "Smaller talent pool than React or Angular", "pricing": "Free (OSS)"},
    {"id": "angular", "name": "Angular", "cat": "Full-stack enterprise framework", "bestFor": "Large enterprise teams wanting enforced architectural consistency across many contributors", "strength": "TypeScript mandatory, comprehensive built-ins (DI, routing, forms, HTTP client, i18n)", "drawback": "Steeper learning curve; more opinionated/rigid structure", "pricing": "Free (OSS)"},
    {"id": "svelte", "name": "Svelte / SvelteKit", "cat": "Compile-time framework", "bestFor": "Apps prioritizing minimal bundle size and fast initial load", "strength": "No virtual DOM — compiles to optimized vanilla JS, dramatically smaller bundles", "drawback": "Smaller ecosystem and talent pool than React/Vue/Angular", "pricing": "Free (OSS)"},
    {"id": "astro", "name": "Astro", "cat": "Framework-agnostic static-site generator", "bestFor": "Content-focused sites — docs, blogs, marketing pages", "strength": "Framework-agnostic, Islands architecture ships JS only for interactive components", "drawback": "Not a fit for highly interactive, app-like experiences", "pricing": "Free (OSS)"},
]


def pick_frontend_vendor(s, fe):
    primary_id = "angular" if "Angular" in fe["v"] else "react"
    return {"v": fe["v"], "why": fe["why"], "primaryId": primary_id, "conf": fe["conf"]}


FRONTEND_NOTE = "React and Next.js are not competing siblings — Next.js is the meta-framework layer that gives React the SSR/routing/API capabilities Vue/Angular/SvelteKit ship natively. index.html's current pickFrontend() only returns React/Angular/Flutter (no Next.js opinion) — pairing React with a meta-framework choice is a reasonable next refinement, not an urgent fix. Source: docs/alternatives-research/04-devops-frontend-cicd-observability-frameworks.md."


# Found via a manual "neither Java nor Python" QA scenario, per the user's own follow-up: a
# bare "not recommended" stub isn't what a human architect would say when the two most common
# defaults are ruled out — they'd name a real alternative. Keyed to the SAME literal strings
# EXCLUSION_TERMS["languages"] can match (plus aliases folded to one entry — "typescript"/
# "node.js"/"nodejs" all count as excluding the "javascript" alternative below), so a language
# the user also explicitly ruled out is never the one suggested in its place.
_LANGUAGE_ALTERNATIVE_ALIASES = {
    "javascript": "javascript", "typescript": "javascript", "node.js": "javascript", "nodejs": "javascript",
    "c#": "csharp", ".net": "csharp",
    "kotlin": "kotlin", "swift": "swift", "rust": "rust", "ruby": "ruby", "php": "php",
}
_LANGUAGE_ALTERNATIVES = {
    "javascript": "JavaScript / TypeScript (Node.js) — runs anywhere a browser does, huge ecosystem, a natural fit for a web-only stack",
    "php": "PHP — fast to deploy, still a huge share of production web backends",
    "ruby": "Ruby (Rails) — fast prototyping, elegant syntax for web apps",
    "go": "Go — simple, fast, built-in concurrency; a strong default for APIs and infrastructure services",
    "rust": "Rust — memory-safe systems performance, the modern choice when C/C++-level speed is the actual requirement",
    "csharp": "C# (.NET) — enterprise-grade tooling and libraries, strong fit for Windows/Azure shops",
    "kotlin": "Kotlin — modern JVM language, a native fit for Android and JVM backends alike",
    "swift": "Swift — the native choice for iOS/macOS apps",
}
# "go" is deliberately absent from EXCLUSION_TERMS["languages"] (see that table's own comment —
# the bare word is too common in ordinary English to trust as an exclusion trigger), so it can
# never appear in excluded_terms and is always safe to fall back to.
_LANGUAGE_ALTERNATIVE_FALLBACK_ORDER = ("go", "javascript", "csharp", "rust", "kotlin", "php", "ruby", "swift")


def _pick_language_alternative(s, excluded_terms):
    """Called when the user ruled out specific backend language(s) by name — recommends a
    real, context-appropriate alternative instead of leaving the category as a bare "not
    recommended" stub. `excluded_terms` is the set of literal EXCLUSION_TERMS["languages"]
    strings that were actually named (see detect_excluded_language_terms), so an alternative
    the user ALSO ruled out ("neither Java, Python, nor Go") is never the one suggested."""
    excluded_alt_keys = {_LANGUAGE_ALTERNATIVE_ALIASES[t] for t in excluded_terms if t in _LANGUAGE_ALTERNATIVE_ALIASES}

    def ok(key):
        return key not in excluded_alt_keys

    picks = []
    if s.get("mobile"):
        if ok("swift"):
            picks.append(_LANGUAGE_ALTERNATIVES["swift"])
        if ok("kotlin"):
            picks.append(_LANGUAGE_ALTERNATIVES["kotlin"])
    if s.get("enterprise") and not picks:
        if ok("csharp"):
            picks.append(_LANGUAGE_ALTERNATIVES["csharp"])
        elif ok("kotlin"):
            picks.append(_LANGUAGE_ALTERNATIVES["kotlin"])
    if (s.get("highScale") or s.get("realtime")) and not picks:
        if ok("go"):
            picks.append(_LANGUAGE_ALTERNATIVES["go"])
        elif ok("rust"):
            picks.append(_LANGUAGE_ALTERNATIVES["rust"])
    if s.get("web") and not picks:
        for key in ("javascript", "go", "php", "ruby"):
            if ok(key):
                picks.append(_LANGUAGE_ALTERNATIVES[key])
                break
    if not picks:
        for key in _LANGUAGE_ALTERNATIVE_FALLBACK_ORDER:
            if ok(key):
                picks.append(_LANGUAGE_ALTERNATIVES[key])
                break

    if not picks:
        # Every alternative this tool knows about was ALSO explicitly excluded by name.
        return {
            "v": "Not recommended — every backend language this tool catalogs an alternative for was excluded",
            "conf": "high", "excluded": True,
            "why": "You ruled out every specific language this tool has a fallback for. Name one you would "
                   "accept, or describe the workload (systems-level, enterprise, mobile, high-throughput) so "
                   "a fit can be suggested.",
        }
    return {
        "v": " · ".join(picks),
        "conf": "medium", "excluded": True,
        "why": "You ruled out the language(s) this tool would otherwise default to — this is a "
               "context-appropriate alternative instead of leaving the category blank.",
    }


def pick_languages(s):
    picks = []
    hits = 0
    if s["javaMentioned"] or s["enterprise"] or s["finance"]:
        picks.append("Java (Spring Boot) for core transactional services")
        if s["javaMentioned"]:
            hits += 1
    if s["pythonMentioned"] or s["agentic"] or s["dataHeavy"] or s["ragNeed"]:
        picks.append("Python (FastAPI) for AI/ML, RAG, and agent orchestration services")
        if s["pythonMentioned"]:
            hits += 1
    if s["goMentioned"] or s["highScale"]:
        picks.append("Go for high-throughput, low-latency infrastructure services")
        if s["goMentioned"]:
            hits += 1
    # Team-gravity signal: only fires on an explicit team-skill match, same style as java/python/go
    # above. This whole block (node/dotnet/ruby/php) was missing from the Python port — found via
    # test_engine_differential.py's rationale-drift ratchet when new corpus cases exercised it.
    known = s.get("known") or {}
    if s["nodeMentioned"]:
        picks.append("Node.js (TypeScript) for services your team already knows" if known.get("node") else "Node.js (TypeScript)")
        hits += 1
    if s["dotnetMentioned"]:
        picks.append(".NET (C#) for services your team already knows")
        hits += 1
    if s["rubyMentioned"]:
        picks.append("Ruby on Rails for services your team already knows")
        hits += 1
    if s["phpMentioned"]:
        picks.append("PHP (Laravel) for services your team already knows")
        hits += 1
    if not picks:
        picks.append("Python (FastAPI) for AI-heavy services, Java (Spring Boot) or Go for core backend")
    return {"v": " · ".join(picks), "why": "Split by workload: Java/Go for performance-critical transactional paths, Python for AI/ML and RAG pipelines where the ecosystem (LangChain, LlamaIndex, etc.) lives. Any language your team already ships in is included even absent a workload-based reason to pick it — matching existing team skills beats a theoretically-better choice on most timelines.", "conf": "high" if hits >= 1 else "medium" if picks else "low"}


def pick_architecture(s):
    hexagonal_note = " In code, hexagonal means: a domain/core layer with zero framework imports (no ORM decorators, no HTTP framework types leaking in), a ports layer of interfaces the domain defines (e.g. a repository interface), and an adapters layer of concrete implementations (the actual Postgres repository, the actual REST controller) that depend inward on the domain — never the reverse. The test that catches violations: your domain layer should compile/type-check with your web framework and database driver both uninstalled."
    if s["minimalProject"] and not s["enterprise"] and not s["largeTeam"]:
        return {"v": "A single simple app — no architecture pattern needed yet", "why": "Hexagonal layering and a modular-monolith split exist to keep future changes cheap in a codebase multiple people will maintain for years. A learning/personal project is one person, changed for weeks — organize by feature if that's comfortable, but introducing ports/adapters boilerplate here is solving a problem you don't have. Worth learning hexagonal architecture as a concept regardless — see the pattern above and the linked note — just not worth applying to this specific project.", "conf": "high"}
    if s["startupMvp"] or s["smallTeam"]:
        why = "Small teams move faster with one deployable unit; hexagonal internal layering keeps a future microservices split cheap."
        if s["enterprise"] or s["compliance"]:
            why += " Compliance/enterprise requirements are met through governance practices (audit logging, strict domain boundaries, IAM) inside this monolith, not by splitting into services your team is too small to operate."
        why += hexagonal_note
        return {"v": "Modular monolith (hexagonal internal structure), split into microservices later", "why": why, "conf": "high"}
    if s["enterprise"] or s["largeTeam"]:
        return {"v": "Microservices with Hexagonal (Ports & Adapters) architecture", "why": "Enterprise scale and multiple teams benefit from independent deployability and clean domain boundaries isolated from infrastructure concerns." + hexagonal_note, "conf": "high"}
    return {"v": "Microservices, hexagonal per bounded context", "why": "Balances scalability with maintainability for a mid-size team and domain." + hexagonal_note, "conf": "low"}


def pick_compute(s):
    ws_note = ""
    if s["liveMultiplayer"]:
        ws_note = " This is a live multiplayer/broadcast workload specifically — confirm your platform holds persistent WebSocket connections correctly: on Cloud Run that means session affinity enabled and min-instances above zero so an active game room's connections don't drop on a cold start; a plain request/response FaaS setup (Lambda without API Gateway WebSocket routes configured) is the wrong default here."
    video_note = ""
    if s["videoConferencing"]:
        video_note = " Video/voice conferencing needs a dedicated media-server tier (SFU) alongside this — see the \"Media server topology\" trade-off card — don't size your general app compute for it; the SFU has its own CPU/bandwidth profile driven by concurrent participant count, not request volume."

    if s["onPrem"]:
        return {"v": "Self-managed Kubernetes on bare metal/VMware — no public-cloud serverless", "why": "Serverless compute (Lambda/Cloud Run) is a public-cloud managed service and isn't available air-gapped/on-prem — self-managed Kubernetes (or a simpler container orchestrator) inside your isolated network is the realistic option.", "conf": "high"}
    if (s["startupMvp"] or s["smallTeam"]) and (s["highScale"] or s["enterprise"] or s["realtime"]):
        return {"v": "Serverless containers (Cloud Run / Fargate) with autoscaling", "why": "Small team and real-time/high-scale/enterprise needs pull in different directions here — managed serverless containers give real autoscaling and container-level control without the ops burden of running your own Kubernetes cluster. Move to full self-managed Kubernetes only once you have dedicated platform engineering capacity." + ws_note + video_note, "conf": "medium"}
    if s["startupMvp"] or (s["smallTeam"] and not s["highScale"]):
        return {"v": "Serverless (Cloud Run / Lambda / Cloud Functions)", "why": "Minimal ops overhead, pay-per-use, ideal for small teams and unpredictable early-stage traffic." + ws_note + video_note, "conf": "high"}
    if s["highScale"] or s["enterprise"] or s["realtime"]:
        return {"v": "Kubernetes (containers) with autoscaling", "why": "Predictable performance, fine-grained resource control, and portability needed at scale or for latency-sensitive workloads." + ws_note + video_note, "conf": "high"}
    return {"v": "Hybrid: serverless for bursty/event-driven work, Kubernetes for core always-on services", "why": "Use the right compute per workload rather than one-size-fits-all." + ws_note + video_note, "conf": "low"}


def pick_messaging(s):
    if s["liveMultiplayer"]:
        return {"v": "Redis Pub/Sub (or a managed realtime service — Ably/Pusher/PubNub) for room broadcast/fan-out — not Kafka", "why": "This is a low-latency broadcast-to-a-room problem (push live scores/state to however many players are in a session right now), not a durable-log problem — Kafka is built for replayable, ordered event history, which adds latency and operational cost this pattern doesn't need and doesn't use. Redis Pub/Sub (already in your stack for caching) or a managed realtime service handles many-subscriber fan-out with much lower latency. Add Kafka separately, later, only if you also want a durable analytics stream of every game event — that's a different, additive need, not a replacement for the broadcast layer.", "conf": "high"}
    if s["collabEditing"]:
        return {"v": "CRDT sync relay (Yjs + y-websocket/Hocuspocus self-hosted, or a managed provider — Liveblocks/PartyKit) — not Kafka, not a generic pub/sub broker", "why": "Concurrent multi-user document edits need conflict-free merge semantics, not just message delivery — a CRDT library (Yjs is the most mature; Automerge and Loro are newer Rust/WASM alternatives with strong JSON/history semantics) does the actual conflict resolution client-side, and the server is a \"dumb\" relay forwarding binary update packets plus periodic snapshot persistence. Presence/cursor data (who's online, cursor position) should ride a separate ephemeral, non-persisted broadcast channel (Yjs Awareness protocol) — never the durable document-update path or a transactional database, since it's high-frequency and disposable. Self-host (y-websocket/Hocuspocus) for control and no per-seat cost, or use a managed provider (Liveblocks, PartyKit) to skip building the relay/persistence layer yourself.", "conf": "high"}
    if s["minimalProject"] and not s["highScale"] and not s["finance"]:
        return {"v": "No message broker needed", "why": "A message broker (even a lightweight one like RabbitMQ) solves problems this project doesn't have yet — background job queues, cross-service async communication, decoupling producers from consumers. A learning/personal project with one process has no producer/consumer split to decouple. If you add a genuinely async task (e.g. sending an email after signup), start with your language's in-process background-job library before reaching for a separate broker.", "conf": "high"}
    picks = []
    hits = 0
    if s["highScale"] or s["realtime"] or s["finance"]:
        picks.append("Kafka (durable, high-throughput event streaming)")
        hits += 1
    if s["gcpShop"]:
        picks.append("Google Pub/Sub (if GCP-native)")
        hits += 1
    if s["startupMvp"] and not s["highScale"]:
        picks.append("Managed queue (SQS/Pub/Sub) rather than self-managed Kafka")
        hits += 1
    if not picks:
        picks.append("RabbitMQ (task queue / flexible routing) for now — move to Kafka if you need durable replay or multiple independent consumer groups")
    return {"v": " · ".join(picks), "why": "Kafka for durable, replayable event streams (audit, fraud, analytics); lighter managed queues/RabbitMQ when volume/ops budget don't justify Kafka yet.", "conf": "high" if hits >= 2 else "medium" if hits == 1 else "low"}


def pick_mesh(s):
    if (s["mtlsMentioned"] or s["compliance"]) and (s["enterprise"] or s["largeTeam"]):
        return {"v": "Istio with SPIFFE/SPIRE-issued workload identity (not just mTLS certs Istio manages internally)", "why": "Istio's built-in mTLS secures the transport, but its default self-managed certificate identity is Istio-internal — it doesn't give you a portable, verifiable workload identity standard auditors or a zero-trust program can reason about independently of your mesh vendor. SPIFFE/SPIRE issues short-lived, cryptographically verifiable identity documents (SVIDs) per workload that Istio can consume, which is the difference between \"traffic between our services happens to be encrypted\" and \"every service call carries a verifiable identity you can write a policy against.\" Worth the added SPIRE-server operational piece specifically because compliance/audit and multi-team trust boundaries are both in play here.", "conf": "high"}
    if s["enterprise"] or s["largeTeam"]:
        return {"v": "Istio", "why": "Multiple services/teams benefit from mTLS, traffic shaping, and observability at the mesh layer.", "conf": "medium"}
    return {"v": "Not needed yet (revisit past ~10-15 services)", "why": "Service mesh adds operational complexity; skip until service count and cross-team traffic policy needs justify it.", "conf": "medium"}


def pick_hybrid_connectivity(s, cloud):
    if s["onPrem"]:
        return {"v": "Not applicable — air-gapped means there is no cloud endpoint to build a dedicated link to", "why": "A dedicated private link (Direct Connect/ExpressRoute-class connectivity) exists to bridge on-prem infrastructure to a cloud provider. An air-gapped/no-public-cloud requirement means there is no cloud side to connect to in the first place.", "conf": "high", "needed": False}
    if not s["hybridConnectivity"]:
        return {"v": "Not required for this scenario", "why": "No hybrid (on-prem + cloud) or dedicated-link requirement detected — a standard internet-facing setup is fine until you specifically need a private, low-latency, high-bandwidth link between your own infrastructure and cloud VPCs.", "conf": "medium", "needed": False}

    vendor = cloud.get("v") or ""
    if "AWS" in vendor:
        link = "AWS Direct Connect"
        transit_hub = "AWS Transit Gateway"
        note = "Terminate on a Transit Gateway if you need to fan the link out to multiple VPCs/accounts rather than a single VPC."
    elif "Azure" in vendor:
        link = "Azure ExpressRoute"
        transit_hub = "Azure Virtual WAN"
        note = "Use Azure Private Peering for VNet connectivity, Microsoft Peering if you also need PaaS/M365 endpoints over the same link."
    elif "Google Cloud" in vendor:
        link = "GCP Cloud Interconnect (Dedicated or Partner)"
        transit_hub = "Network Connectivity Center"
        note = "GCP's 99.99% SLA requires two attachments across two independent metros — a single attachment does not meet it."
    elif "Huawei" in vendor:
        link = "Huawei Cloud Direct Connect (DC)"
        transit_hub = "Huawei Cloud Enterprise Router (ER)"
        note = "The Enterprise Router aggregates routes across multiple VPCs the way Transit Gateway/Virtual WAN do for AWS/Azure."
    else:
        link = "your cloud provider's dedicated-interconnect service (AWS Direct Connect / Azure ExpressRoute / GCP Cloud Interconnect / Huawei Direct Connect)"
        transit_hub = "the matching transit-hub service"
        note = "Pick the specific service once the cloud provider is confirmed — they are not interchangeable at the provisioning level."

    return {
        "v": f"{link} + {transit_hub}, with a Site-to-Site VPN as an automatic failover path",
        "why": f"Hybrid connectivity detected — {link} gives a dedicated, low-latency, high-bandwidth private link instead of routing on-prem-to-cloud traffic over the public internet. {note} Keep a Site-to-Site VPN (IPsec) on standby: cloud providers prioritize the dedicated link automatically by default routing preference, so the VPN only takes over if the dedicated link fails — advertise identical CIDR blocks on both so failover doesn't need a manual route change. For encryption in transit beyond the VPN's IPsec overlay, enable MACsec directly on the dedicated link if your circuit tier supports it (line-rate, no additional latency).",
        "conf": "high",
        "needed": True,
    }


# -------------------------------------------------------------------------------------------
# The six functions below mirror index.html's pickAuditLogging/pickPrivilegedAccess/
# pickTestingStrategy/pickNetworkBoundary/pickMultiCloudBridging/pickSecurityGates exactly —
# see that file's comment above pickAuditLogging() for why they exist (promoting target-design
# KB docs 12/13/15/16/17/18 into real categories so /api/refine, /api/ask and the MCP tool can
# reach them, closing the gap PRD Section 12 records under "Follow-up: RAG-derived stack
# reasoning"). Doc 14 has no matching function here either, for the same reason stated there.
# -------------------------------------------------------------------------------------------

def pick_audit_logging(s):
    if s["minimalProject"] and not s["compliance"] and not s["enterprise"] and not s["finance"] and not s["healthcare"]:
        return {"v": "Application logs are enough for now — no dedicated audit pipeline needed", "why": "A learning/personal project has no regulator or auditor asking \"who did what, to what data, when\" — that question, not debugging, is what a dedicated audit pipeline exists to answer. Revisit if this ever handles real user data or gains a compliance obligation.", "conf": "high"}
    if s["compliance"] or s["finance"] or s["healthcare"] or (s["enterprise"] and s["largeTeam"]):
        return {"v": "Separate immutable audit pipeline (WORM storage, years retention) — distinct from application logs", "why": "Application logs are sampled, retained for weeks, and exist for debugging; audit events (who did what, to what data, when) must be complete — never sampled — immutable, and tamper-evident, because they answer a regulator, not an engineer. An audit log an administrator can delete is not an audit log. Route infrastructure-level and data-access events to the same write-once store so both are answerable from one place, and enforce shipping by policy rather than convention — a setting a team can forget to enable is a control that exists on paper, not in the estate.", "conf": "high"}
    return {"v": "Application logs today; add a dedicated immutable audit pipeline once you have real user data or a compliance obligation", "why": "Structured application logs (retained weeks, sampled) cover debugging at this stage. A separate audit pipeline is worth the operational cost once there is a specific regulator, customer contract, or data-handling obligation asking \"who did what\" — building it earlier is real infrastructure with no one asking the question it answers yet.", "conf": "medium"}


def pick_privileged_access(s):
    if s["onPrem"]:
        return {"v": "Bastion host, no public SSH/RDP; JIT-elevated local admin group membership, every elevation logged", "why": "The cloud-native pattern (PIM against a cloud IdP) assumes a cloud identity provider reachable from wherever an engineer is — an air-gapped environment needs the equivalent enforced locally: a bastion as the only path in, group membership granted for a bounded window rather than held standing, and elevation events logged to the same audit pipeline as everything else.", "conf": "high"}
    if s["minimalProject"] and not s["compliance"] and not s["enterprise"]:
        return {"v": "No formal privileged-access process needed — you are the only administrator", "why": "Just-in-time elevation, break-glass accounts, and access reviews exist to answer \"who had admin, when, and can we prove it\" across a TEAM of people with standing access to revoke. A solo learning project has no second admin to segregate duties from and no review to conduct. Revisit the moment a second person gets infrastructure access.", "conf": "high"}
    if s["compliance"] or s["finance"] or s["healthcare"] or s["enterprise"]:
        return {"v": "Just-in-time elevation (PIM) — no standing admin; time-boxed, approved, MFA'd, auto-expiring, every activation logged", "why": "Standing privileged access and shared accounts are the most common real finding in an infrastructure access review — if nobody had to ask for admin, nobody can prove why they had it during an incident. Pair JIT elevation with a small, fixed number of monitored break-glass accounts (excluded from conditional access, hardware MFA, alerted on any use) and periodic access recertification, with segregation of duties so the approver is never the requester. Critically, treat access to production DATA as a separate, higher grant from infrastructure access — a DBA with legitimate cluster access querying live customer records is its own auditable event, ideally with dynamic data masking so even an authorized query returns masked PII unless the specific need is explicit. Access to the box is not access to the data.", "conf": "high"}
    return {"v": "A small, named set of infra admins with a shared secrets manager — add JIT elevation once the team or the compliance surface grows", "why": "Formal just-in-time elevation earns its operational cost once there are enough infrastructure admins that \"who has access\" stops being answerable from memory, or once a customer/regulator starts asking. Below that, a small named admin list with credentials in a proper secrets manager (never shared plaintext) is proportionate. Revisit if headcount with infra access grows past a handful, or a compliance requirement appears.", "conf": "medium"}


def pick_testing_strategy(s):
    if s["minimalProject"]:
        return {"v": "Unit tests for core logic, a handful of integration tests — skip the rest for now", "why": "A test pyramid, named performance-test types, and a formal test-data strategy exist to manage risk across a codebase multiple people maintain under real load with real user data. A learning/personal project has none of those — unit tests catching regressions in core logic is genuinely proportionate; contract tests, load/stress/soak/spike testing, and masked-production test data all solve problems this scale does not have yet.", "conf": "high"}
    # Two independent flags, each contributing its OWN v-summary fragment — not two booleans
    # collapsed into one length check. The original version gated the "+ masked/synthetic
    # test-data strategy" suffix on `len(notes) > 1` rather than on whether that specific note
    # fired, so a compliance-only case (high_scale false, one note from compliance) produced a
    # `v` of "Test pyramid (unit-heavy)" with no visible reason for 'high' confidence — and the
    # JS side had the matching bug, producing a dangling "+ " instead. Caught by the JS<->Python
    # differential harness (test_engine_differential.py) when these categories were added to it.
    high_scale_note = s["highScale"]
    data_strategy_note = (s["compliance"] or s["finance"] or s["healthcare"]) and not s["minimalProject"]
    notes = []
    if high_scale_note:
        notes.append("load testing (expected peak) and soak testing (sustained hours — the type most teams skip, and the one that finds a memory leak) before you trust an autoscaling threshold")
    if data_strategy_note:
        notes.append("test data must never include real production records in a lower environment — synthetic data for volume, a masked and subsetted production slice for edge-case realism")
    why = ('Unit tests (fast, most of the suite) at the base, integration tests against real dependencies, '
           'contract tests between services once there is more than one, few end-to-end tests at the top — '
           'the inverted shape ("ice-cream cone": mostly E2E, few units) is slow, flaky, and eventually ignored.')
    if notes:
        why += " At your scale, also: " + "; ".join(notes) + "."
    why += (' A successful "backup completed" log is not evidence of a working restore — the only proof is '
            'an actual restore drill, which matters more the more this system\'s data would hurt to lose.')
    v_parts = ["Test pyramid (unit-heavy)"]
    if high_scale_note:
        v_parts.append("load/soak testing")
    if data_strategy_note:
        v_parts.append("masked/synthetic test-data strategy")
    v = " + ".join(v_parts) if notes else "Test pyramid: unit-heavy, integration + contract tests as services multiply, few E2E"
    return {"v": v, "why": why, "conf": "high" if notes else "medium"}


def pick_network_boundary(s):
    if s["onPrem"]:
        return {"v": "Not applicable — air-gapped means every dependency is already inside your own network boundary", "why": "Private-endpoint architecture exists to keep traffic to managed CLOUD services off the public internet. An air-gapped environment has no cloud services to reach in the first place — everything is already inside the boundary by construction.", "conf": "high"}
    if s["minimalProject"] and not s["compliance"]:
        return {"v": "No private-endpoint architecture needed — a single small deployment has no internal boundary to protect", "why": "Private endpoints, an egress allowlist, and a single audited exit point are controls for an estate with multiple services and a real internal attack surface. One small deployment calling its own managed database over the provider's default secure connection has nothing further to gain from this — the added networking complexity would have no corresponding benefit yet.", "conf": "high"}
    if s["compliance"] or s["finance"] or s["healthcare"]:
        return {"v": "Private endpoints for every managed cloud service (database, cache, secrets, LLM); one egress gateway with a per-host allowlist for genuine third parties", "why": "Managed cloud services (database, cache, secrets manager, and — specifically relevant if an LLM call is in the request path — the cloud's own model endpoint) reached over a private link never transit the public internet, which is what makes \"the model call never left our network\" literally true rather than a compliance talking point. Genuine third parties (a payment gateway, an SMS provider) have no private-link option and must exit through one audited, allowlisted gateway — a compromised workload should not be able to open an arbitrary internet connection.", "conf": "high"}
    return {"v": "Default provider networking is fine for now; move to private endpoints once a specific service or compliance need requires it", "why": "Most managed cloud services are already reasonably secured by default (TLS in transit, provider-side auth). Private-endpoint architecture is worth the added complexity once there is a specific reason — a compliance requirement, a genuinely sensitive dependency, or enough services that an internal attack surface actually exists — not as a default for every deployment.", "conf": "medium"}


def pick_multi_cloud_bridging(s):
    if not s["multiCloudMentioned"] or s["onPrem"]:
        return {"v": "Not applicable — single cloud provider in use", "why": "Left to choose freely, compute and data belong in the same cloud — every call that crosses between providers costs latency and usually egress fees a single-cloud design does not pay at all. This category only has something to say once a real multi-cloud split is on the table.", "conf": "medium", "needed": False}
    return {"v": "Constraint-driven split only — one IaC source across both providers, a dedicated interconnect (not a public-internet path) for real data volume, workload identity federation for cross-cloud auth", "why": "A split-provider architecture should be justified by a named hard constraint (data-residency law, an org/M&A mandate, or one provider-specific service) — not by \"avoiding lock-in\" as a general principle, which trades a real risk for a smaller, harder-to-name one while paying the ongoing cross-cloud tax regardless. One Terraform (or equivalent) configuration invoking both providers keeps the highest-risk part — the cross-cloud link and identity federation — reviewable in one place rather than split across two independently-reviewed pipelines. For real data volume between providers, a dedicated interconnect (not a site-to-site VPN over the public internet) gives predictable, SLA-backed latency. Authenticate across the boundary via workload identity federation — a short-lived token issued on proof of what the workload is — never a stored credential for the second cloud. Mitigate the latency that cannot be removed: cache on the compute side, and push anything that tolerates delay onto an async path rather than a synchronous cross-cloud call.", "conf": "high", "needed": True}


def pick_security_gates(s):
    if s["minimalProject"]:
        return {"v": "Secrets scanning + dependency scanning on every push — skip the rest for now", "why": "The full pipeline-security-gate set (SAST, DAST, image scanning, signing, SBOM generation, a human-approved promotion step) is proportionate to a codebase multiple people maintain, handling real user data, under a change-management obligation. A learning project has none of those yet — a free secrets scanner (catches an accidentally committed API key, the single most damaging mistake at any scale) and dependency scanning cost nothing to add and catch the mistakes that actually happen at this size.", "conf": "high"}
    if s["compliance"] or s["finance"] or s["healthcare"] or s["enterprise"]:
        return {"v": "Full gate set at the PR (secrets, SAST, SCA, image scan, sign + SBOM) — GitOps promotion with a human-approved step before production, canary with SLO-gated auto-rollback", "why": "A vulnerability caught at the pull request costs minutes; the same vulnerability in production is an incident and an audit finding — gate placement is a cost decision, not a purity one. A green pipeline is a precondition to merge, never an authorisation to reach production: that promotion needs a human whose approval is a different person from the change's author (segregation of duties), which is exactly the control a regulated reviewer checks for. Admission control at the cluster edge (rejecting unsigned images, privileged pods, no-limits workloads) is what makes the earlier gates real controls rather than advisory scans — a pipeline can be bypassed, an admission policy enforced at the cluster cannot be without an audited change.", "conf": "high"}
    return {"v": "Secrets scanning, dependency scanning, and unit tests as required PR checks; add SAST/DAST/signing as the team or the data sensitivity grows", "why": "The gate set scales with what is actually at stake. Secrets and dependency scanning are cheap and catch the two most common real mistakes (a leaked credential, a known-vulnerable package) regardless of scale. The heavier gates (SAST, DAST, image signing, SBOM generation) earn their operational cost once there is a compliance obligation or an external audit to satisfy — add them deliberately, not by default.", "conf": "medium"}


def pick_cache(s):
    # This ignored `s` entirely and returned Redis unconditionally, so a static site or a
    # notebook-only ML script got a cache tier it has no use for. Redis is still right when a
    # cache is warranted — the fix is requiring a reason, not changing the product.
    reasons = []
    if s["redisMentioned"]:
        reasons.append("you already use Redis")
    if s["highScale"]:
        reasons.append("high traffic/volume")
    if s["realtime"]:
        reasons.append("real-time/low-latency paths")
    if s["ecommerce"]:
        reasons.append("e-commerce catalog and cart reads")
    if s["liveMultiplayer"]:
        reasons.append("live session/leaderboard state")
    if s["chatbot"] or s["ragNeed"]:
        reasons.append("repeated LLM/retrieval calls worth caching")
    if s["enterprise"] or s["largeTeam"]:
        reasons.append("session storage across multiple services")
    if s["geospatial"]:
        reasons.append("ephemeral live-location state")

    if not reasons:
        return {"v": "Not required yet", "conf": "medium", "needed": False,
                "why": "Nothing in the requirement implies a caching tier — no high traffic, real-time "
                       "path, shared session state, or repeated expensive lookup was detected. Adding "
                       "Redis here would be infrastructure to run and pay for with no load to justify "
                       "it. Revisit when you have a measured hot path; Redis is the default choice at "
                       "that point."}
    return {"v": "Redis", "conf": "high", "needed": True,
            "why": "De facto standard for caching, session storage, rate limiting, and lightweight "
                   "pub/sub. Recommended here because of " + ", ".join(reasons) + "."}


def pick_database(s):
    if (s["minimalProject"] and not s["highScale"] and not s["compliance"] and not s["finance"]
            and not s["mongoMentioned"] and not s["unstructured"]):
        return {"v": "SQLite — a single file, zero setup or hosting", "why": "A learning/personal project with one user (or a handful) doesn't need a database SERVER at all — SQLite gives you real SQL, transactions, and a schema in a single file with no service to run, no connection string, no hosting cost. Move to PostgreSQL when you need concurrent writers from multiple server instances, which a single small deployment doesn't have.", "conf": "high"}
    if s["liveMultiplayer"]:
        return {"v": "Redis (in-memory, sorted sets) as the primary store for live session/leaderboard state · PostgreSQL or a NoSQL document store for post-session history only", "why": "Live leaderboard/game-room state is read and written by every participant multiple times per second — that's an in-memory-data-structure problem, not a transactional (Postgres) or flexible-document (Firestore-style NoSQL) problem. Redis sorted sets (ZADD/ZRANGE) give O(log N) rank updates and reads, which is what a real-time leaderboard actually needs. A document database used the \"obvious\" way here — one shared leaderboard document updated by every player — hits real per-document write-contention limits (roughly 1-10 sustained writes/sec/document is the safe range before Firestore-class stores need a distributed-counter sharding workaround) well before a live session's write rate. Once a session ends, write the final results to a normal persisted store (Postgres for relational history/analytics, or a NoSQL document store if the shape is simpler) — that's a completely different access pattern (low-frequency, durable) from the live path, so it's fine for it to use a completely different store.", "conf": "high"}
    if s["feedFanout"] and s["highScale"]:
        return {"v": "Cassandra or DynamoDB (wide-column, precomputed per-user feed) as the primary feed store · PostgreSQL for user/social-graph relational data", "why": "A news feed at real scale is a fan-out problem, not a relational-query problem: one post from a followed account needs to land in every follower's feed. Precomputing each user's feed as a wide-column partition (fan-out-on-write) at post time is what Cassandra/ScyllaDB/DynamoDB are built for, and is how this is actually done at scale (this is the standard Twitter/Instagram-class pattern) — a relational store would need an expensive real-time join/aggregation per feed load instead. Keep the social graph itself (who-follows-whom, profile data) in Postgres — that part is genuinely relational and doesn't have the fan-out write-amplification problem.", "conf": "high"}

    picks = []
    hits = 0
    warehouse_need = s["dataHeavy"] and not s["structured"] and not s["chatbot"] and not s["ragNeed"]
    if warehouse_need:
        picks.append("Cloud data warehouse (BigQuery / Snowflake / Redshift) as the analytics store")
        hits += 1
    # Team-skill RDBMS choice: a SINGLE relational store, not "Postgres AND MySQL AND Oracle"
    # stacked as if all are primary at once — pick whichever specific one the team already knows
    # (fixed check order, since a team realistically names one; Postgres stays the fallback).
    # This whole block, and the `not mongoMentioned` guard below, existed only in index.html: a
    # requirement naming an existing MongoDB estate got MongoDB alone in the browser and
    # "PostgreSQL · MongoDB" from the backend.
    rdbms_name, rdbms_skill_note = "PostgreSQL", ""
    if s["mysqlMentioned"]:
        rdbms_name, rdbms_skill_note = "MySQL", " — matches your team's existing MySQL experience"
    elif s["sqlServerMentioned"]:
        rdbms_name, rdbms_skill_note = "Microsoft SQL Server", " — matches your team's existing SQL Server experience"
    elif s["oracleDbMentioned"]:
        rdbms_name, rdbms_skill_note = "Oracle Database", " — matches your team's existing Oracle experience"
    rdbms_skill_hit = s["mysqlMentioned"] or s["sqlServerMentioned"] or s["oracleDbMentioned"]

    if (s["structured"] or s["finance"] or s["postgresMentioned"] or rdbms_skill_hit
            or (not s["unstructured"] and not warehouse_need and not s["mongoMentioned"])):
        picks.append(f"{rdbms_name} (primary transactional store){rdbms_skill_note}")
        if s["structured"] or s["finance"] or s["postgresMentioned"] or rdbms_skill_hit:
            hits += 1
    if s["unstructured"] or s["chatbot"] or s["ragNeed"] or s["mongoMentioned"]:
        picks.append("MongoDB (flexible schema for content, chat history, documents)")
        if s["unstructured"] or s["mongoMentioned"]:
            hits += 1
    if s["iot"] or (s["highScale"] and s["dataHeavy"]):
        picks.append("Cassandra (write-heavy, high-scale, multi-region time-series/event data)")
        hits += 1
    if not picks:
        picks.append("PostgreSQL as primary store")
    why = (
        "Your workload reads as analytics/ETL/reporting-centric rather than transactional — a columnar cloud warehouse is built for exactly that (large scans, aggregations, BI-tool integration), which Postgres/Mongo/Cassandra are not optimized for. Add Postgres alongside it only if you also have an operational/transactional app component; add Cassandra alongside it if you also have high-volume write ingestion (e.g. IoT/event streams) feeding the warehouse."
        if warehouse_need
        else f"{rdbms_name} for relational/transactional integrity, MongoDB for flexible document data, Cassandra only when write volume and multi-region needs exceed what {rdbms_name}/Mongo comfortably handle."
    )
    if s["postgresMentioned"] or s["mongoMentioned"] or rdbms_skill_hit:
        why += " Included because your team already knows " + " and ".join(
            [n for n in [s["postgresMentioned"] and "Postgres", s["mysqlMentioned"] and "MySQL",
                         s["sqlServerMentioned"] and "SQL Server", s["oracleDbMentioned"] and "Oracle",
                         s["mongoMentioned"] and "MongoDB"] if n]
        ) + " — matching existing skills beats a theoretically-better choice on most timelines."
    if s["geospatial"]:
        why += " Geospatial note: enable the PostGIS extension on Postgres for indexed nearest-neighbor/radius queries (e.g. \"drivers within 2km\") — plain Postgres without PostGIS will do this with slow full-table scans. For a live, constantly-updating position feed specifically (a driver's current location, not trip history), treat that as ephemeral state in Redis (GEOADD/GEOSEARCH) rather than writing every position update to Postgres — same reasoning as the live-leaderboard pattern: high-frequency writes to a shared/near-shared key belong in an in-memory store, with Postgres holding the durable trip/ride record instead."
    return {"v": " · ".join(picks), "why": why, "conf": "high" if hits >= 1 else "medium"}


def pick_containers(s):
    if s["openshiftMentioned"]:
        return {"v": "Docker + OpenShift (Red Hat's enterprise Kubernetes distribution)" + (", self-managed" if s["onPrem"] else ""), "why": "Your team already knows OpenShift — staying on it avoids retraining onto a different Kubernetes distribution for no real workload-driven reason, and OpenShift genuinely supports both on-prem and cloud deployment.", "conf": "high"}
    if s["onPrem"]:
        return {"v": "Docker + self-managed Kubernetes (kubeadm/Rancher/RKE2 on bare metal or VMware) — not EKS/GKE/AKS", "why": "Managed Kubernetes offerings are public-cloud services; an air-gapped/on-prem environment needs a self-managed distribution you can run entirely inside your network boundary.", "conf": "high"}
    if s["huaweiShop"]:
        return {"v": "Docker + Huawei Cloud CCE (Cloud Container Engine)" + (", CCE Turbo for high-throughput networking" if s["highScale"] else ""), "why": "Explicit Huawei Cloud usage detected — CCE is Huawei's managed Kubernetes offering, matching your existing cloud footprint rather than introducing a second vendor.", "conf": "high"}
    if s["minimalProject"] and not s["highScale"] and not s["enterprise"]:
        return {"v": "No orchestrator needed — run the app directly, or in a single Docker container if you want portability", "why": "Kubernetes exists to schedule and scale MANY container instances across MANY machines — a learning/personal project runs one instance on one machine, which is exactly the case an orchestrator adds operational overhead to without solving anything. A single Dockerfile (optional, mainly for \"works on my machine\" portability) is as far as containerization needs to go here.", "conf": "high"}
    if s["startupMvp"]:
        return {"v": "Docker + managed serverless containers (Cloud Run / Fargate)", "why": "Keep container benefits without managing a Kubernetes control plane.", "conf": "high"}
    why = "Standard for portable, scalable container orchestration once team/scale justify it."
    conf = "high" if (s["enterprise"] or s["highScale"]) else "medium"
    known = s.get("known") or {}
    if known.get("docker") or known.get("kubernetes"):
        names = " and ".join([n for n in [known.get("docker") and "Docker", known.get("kubernetes") and "Kubernetes"] if n])
        why += f" Your team already knows {names} — this isn't introducing a new skillset."
        conf = "high"
    return {"v": "Docker + Kubernetes (EKS/GKE/AKS matching chosen cloud)", "why": why, "conf": conf}


def pick_observability(s):
    if s["onPrem"]:
        return {"v": "OpenTelemetry (instrumentation standard) + self-hosted Grafana + Prometheus + Loki (or ELK/OpenSearch)", "why": "SaaS observability platforms (Datadog, Splunk Cloud, Dynatrace SaaS) require sending telemetry to the vendor's cloud, which an air-gapped network can't reach — self-hosted OSS observability is the only realistic option inside the boundary.", "conf": "high"}
    if s["minimalProject"] and not s["enterprise"] and not s["highScale"]:
        return {"v": "Console/platform logs — no observability vendor", "why": "Datadog and similar platforms exist to correlate metrics/logs/traces across many services under real production load — a single small deployment has neither the service count nor the traffic to need that. Your PaaS's built-in logs plus a free-tier error tracker (Sentry's free tier is genuinely usable at this scale) covers debugging a live issue. Add a real observability platform once you have multiple services or on-call obligations.", "conf": "high"}
    apm = "Datadog"
    why = "Best all-around breadth (APM, logs, infra, RUM) with fastest time-to-value."
    conf = "low"
    if s["enterprise"] and s["compliance"]:
        apm, why, conf = "Splunk (+ Datadog or Dynatrace for APM)", "Enterprises with heavy compliance/audit needs often standardize log management on Splunk alongside a dedicated APM tool.", "high"
    elif s["enterprise"] and s["highScale"]:
        apm, why, conf = "Dynatrace", "Strong automatic root-cause analysis (AI-assisted) valuable at large, complex enterprise scale.", "high"
    elif s["prometheusMentioned"]:
        apm, why, conf = "Grafana + Prometheus (OSS)", "Your team already runs Prometheus/Grafana — sticking with what they know beats introducing a new SaaS vendor and its onboarding cost.", "high"
    elif s["datadogMentioned"]:
        apm, why, conf = "Datadog", "Your team already has Datadog experience — matching existing familiarity over evaluating a new vendor.", "high"
    elif s["splunkMentioned"]:
        apm, why, conf = "Splunk (+ a dedicated APM tool for tracing/metrics)", "Your team already runs Splunk for log management — keep it and add a focused APM tool alongside rather than replacing an established platform.", "high"
    elif s["dynatraceMentioned"]:
        apm, why, conf = "Dynatrace", "Your team already has Dynatrace experience — matching existing familiarity over evaluating a new vendor.", "high"
    elif s["newrelicMentioned"]:
        apm, why, conf = "New Relic", "Your team already knows New Relic — sticking with it avoids a vendor migration with no workload-driven reason to switch.", "high"
    elif s["elkMentioned"]:
        apm, why, conf = "Elastic Stack (Elasticsearch + Kibana)", "Your team already runs the Elastic Stack — a solid self-hosted or Elastic Cloud log/observability platform, no need to introduce a second one.", "high"
    elif s["huaweiShop"]:
        apm, why, conf = "Huawei Cloud Eye (CES) + LTS (Log Tank Service)", "Explicit Huawei Cloud usage detected — Cloud Eye covers metrics/health monitoring and LTS covers centralized logging natively on Huawei Cloud, matching your existing footprint rather than adding an external SaaS vendor.", "high"
    elif s["startupMvp"]:
        apm, why, conf = "Grafana + Prometheus (OSS) or Datadog free tier", "Lower cost for a small team; upgrade to Datadog/Dynatrace as scale and budget grow.", "medium"
    return {"v": f"OpenTelemetry (instrumentation standard) + {apm}", "why": f"Instrument everything with OpenTelemetry (vendor-neutral) and ship to {apm.split(' ')[0]}. {why}", "conf": conf}


def pick_frontend(s):
    picks = []
    hits = 0
    if s["web"] or (not s["mobile"]):
        picks.append("Angular" if s["enterprise"] else "React")
        if s["web"]:
            hits += 1
    if s["mobile"]:
        picks.append("Flutter (single codebase for iOS + Android)")
        hits += 1
    if not picks:
        picks.append("React")
    return {"v": " + ".join(picks), "why": "React for fastest ecosystem/hiring fit (Angular if already an enterprise Angular shop); Flutter when both iOS and Android are needed from one codebase.", "conf": "high" if hits >= 1 else "low"}


def pick_llm(s):
    picks = []
    if s["compliance"] or s["enterprise"] or s["security"]:
        picks.append({"name": "Anthropic Claude (Sonnet tier)", "tag": "Primary reasoning / user-facing — strong safety & instruction following for regulated use cases"})
    else:
        picks.append({"name": "OpenAI GPT (mid tier, e.g. GPT-4o class)", "tag": "Primary reasoning / user-facing — broad tool ecosystem"})
    if s["agentic"]:
        picks.append({"name": "Anthropic Claude or OpenAI GPT (large/frontier tier)", "tag": "Agentic tool-use & multi-step orchestration — pick the strongest tool-calling model available"})
    if s["highScale"] or s["startupMvp"]:
        picks.append({"name": "Open-weight small model — 4B–12B (Google Gemma, DeepSeek, or Llama class)", "tag": "High-volume, low-cost tasks: classification, extraction, simple chat, routing"})
    if s["dataHeavy"] or s["ragNeed"]:
        picks.append({"name": "Mid-size open-weight — 12B–30B (DeepSeek-V/R series, Gemma 27B)", "tag": "Cost-efficient RAG answer generation and summarization at scale"})
    if len(picks) < 2:
        picks.append({"name": "Google Gemini (Flash tier) or Gemma 4B–12B", "tag": "Cheap, fast fallback/secondary model for simple tasks"})
    return picks


def pick_mcp(s):
    picks = []
    if s["knowledgeBase"] or s["ragNeed"]:
        picks.append("Knowledge/RAG MCP server (exposes document search & retrieval as tools)")
    if s["agentic"]:
        picks.append("Multi-tool orchestration MCP server (Jira, email, calendar, internal APIs as callable tools)")
    if s["enterprise"]:
        picks.append("Internal data-source MCP servers (databases, CRMs, ticketing) with RBAC-scoped tool access")
    if not picks:
        picks.append("Lightweight internal-tools MCP server exposing your core APIs as callable tools")
    return picks


def pick_integration_guidance(s):
    # Pattern #2 (omnichannel) is architecturally different from pattern #1 (chatbot-only), not
    # a bigger version of it — the hard part isn't the model, it's a channel-routing/session-
    # continuity layer sitting in front of one AI core. Branch the whole guidance set, not just
    # patch individual fields, so the omnichannel case doesn't inherit chatbot-only assumptions
    # (e.g. "one webhook route" is simply wrong once there are multiple channel adapters).
    if s["brownfieldOmnichannel"]:
        integration_path = (
            {"v": "Internal channel-routing service — no public webhooks", "why": "An air-gapped/on-prem existing system has no public ingress for any channel adapter to call. The routing layer and every channel adapter it fronts (web widget, WhatsApp, email, voice/IVR) have to run inside the same network boundary — some channels (WhatsApp Business API, public voice carriers) fundamentally require internet reachability, so confirm which channels are actually in scope before committing to full air-gap for all of them."}
            if s["onPrem"] else
            {"v": "A channel-routing/orchestration layer in front of one shared AI core, with a distinct adapter per channel (web widget, WhatsApp Business API, email, voice/IVR)", "why": "This is the piece pattern #1 doesn't need: each channel has its own message format, delivery guarantees, and identity model (a phone number for WhatsApp, an email address, a session cookie for the widget) — the routing layer's job is normalizing all of that into one representation before it ever reaches the AI core, and translating the core's response back into each channel's native format."}
        )
        auth_note = "Each channel authenticates differently (WhatsApp verifies phone numbers, email has no real-time auth at all, your web widget can reuse existing session cookies) — resolve every channel's identity to the SAME internal user/session ID at the routing layer, before the AI core ever sees the request. The AI core should never need to know which channel a message arrived on to identify who's asking."
        session_note = "This is the hardest part of pattern #2, worth calling out explicitly: session/conversation state must be keyed by the resolved internal user ID (not per-channel), so a conversation started on the web widget and continued over WhatsApp is the SAME conversation, not two. Store it centrally (one session store the routing layer and AI core both read/write), not per-channel-adapter — a per-channel session store is exactly how \"channel amnesia\" (the bot forgetting context when a user switches channels) happens in practice."
        scope_note = (
            "Scope what the AI core can see and do explicitly, same as pattern #1 — but also scope each CHANNEL ADAPTER's permissions independently (e.g. the email adapter shouldn't be able to trigger actions only the authenticated web-widget channel should allow), since channels carry different trust levels for the same underlying user."
            if s["compliance"] else
            "Give the routing layer its own scoped credentials against your existing backend, and treat each channel adapter as a separate trust boundary — a compromised WhatsApp webhook shouldn't have the same blast radius as a compromised authenticated web-widget session."
        )
        return {"integrationPath": integration_path, "authNote": auth_note, "sessionNote": session_note, "scopeNote": scope_note, "patternLabel": "omnichannel AI support", "patternAssumption": "This section assumes pattern #2 — omnichannel AI support across multiple channels sharing one AI core. Pattern #1 (single-channel chatbot) uses simpler, single-webhook guidance instead — you'll see that version if you pick that pattern. Event-driven notification/feedback engines and per-microservice-vs-centralized AI gateway patterns are real, different architectures — not built yet, flagged rather than force-fit into this guidance."}

    integration_path = (
        {"v": "Internal service call — no public webhook", "why": "An air-gapped/on-prem existing system has no public ingress to receive a webhook from; the chatbot service has to be deployed inside the same network boundary and called as an internal service (gRPC/REST over your private network), not integrated via an external callback URL."}
        if s["onPrem"] else
        {"v": "A new API route or webhook on your existing backend, calling out to the chatbot service", "why": "The chatbot doesn't need to live inside your existing application's codebase — a thin new route (e.g. POST /api/chat) that proxies to a separately-deployed chatbot service keeps the integration surface small and the two deployable independently. Avoids a large refactor of code that's already working."}
    )
    auth_note = (
        "Pass your existing auth/session token through to the chatbot service on every request rather than issuing a separate credential — a second auth system is exactly the kind of surface-area growth that turns a small integration into a compliance review."
        if (s["compliance"] or s["enterprise"]) else
        "Reuse whatever session/auth mechanism your existing app already has — a chatbot-specific login system is unnecessary complexity for what's fundamentally a new feature on an existing account."
    )
    session_note = "Conversation history needs its own storage — a lightweight table/collection keyed by your existing user ID (or a signed anonymous session ID for logged-out visitors), separate from your main application data. It doesn't need to live in your primary database; a small dedicated store (even Redis with a TTL for short-lived sessions) is usually simpler than bolting new tables onto a schema you didn't design for this."
    scope_note = (
        "Scope what the chatbot can see and do explicitly — for a regulated existing system, the chatbot should read from a defined, reviewed subset of your data (via an API your team controls), never given direct database access. That boundary is also what makes the Guardrails section below enforceable."
        if s["compliance"] else
        "Give the chatbot service its own scoped API key/credentials against your existing backend — least-privilege, not the same credentials your main application uses internally."
    )
    return {"integrationPath": integration_path, "authNote": auth_note, "sessionNote": session_note, "scopeNote": scope_note, "patternLabel": "chatbot / conversational assistant", "patternAssumption": "This section assumes pattern #1 — a standalone chatbot bolted onto one existing application. Omnichannel AI support uses a different, channel-routing-focused version of this guidance instead — you'll see that version if you pick that pattern. Event-driven notification/feedback engines and per-microservice-vs-centralized AI gateway patterns are real, different architectures — not built yet, flagged rather than force-fit into this guidance."}


RAG_TYPES = [
    "Naive RAG", "Retrieve-and-Rerank RAG", "Hybrid (keyword + vector) RAG", "Hierarchical / Multi-level RAG",
    "Graph RAG (knowledge-graph grounded)", "Agentic RAG (agent decides when/what to retrieve)", "Corrective RAG (CRAG, validates retrieved docs)",
    "Self-RAG (model critiques its own retrieval)", "Adaptive RAG (routes query to best retrieval strategy)", "Multi-hop RAG (chained retrieval for complex questions)",
    "Fusion RAG / RAG-Fusion (multiple query rewrites, merged results)", "Modular RAG (composable retrieval/generation pipeline)",
    "Structured/SQL RAG (retrieval over databases, not just documents)", "Long-context (retrieval-free, full-document-in-context)",
]


def pick_rag(s):
    if not s["ragNeed"] and not s["chatbot"] and not s["knowledgeBase"]:
        return {"name": "RAG likely not required", "why": "No knowledge-base / document-search need detected. If the assistant only needs general reasoning (no proprietary data lookup), skip RAG and rely on the base LLM, or add it later.", "conf": "medium"}
    if s["structured"] and not s["unstructured"]:
        return {"name": RAG_TYPES[12], "why": "Data lives in structured/relational stores — retrieval should query the database (text-to-SQL or schema-aware retrieval) rather than chunked documents.", "conf": "high"}
    if s["agentic"] and (s["compliance"] or s["healthcare"]):
        return {"name": RAG_TYPES[5] + " + Corrective RAG (CRAG) validation layer", "why": "Agentic workflow in a compliance/clinical context needs both properties, not just one: let the agent decide dynamically when/what to retrieve (Agentic RAG), but also validate every retrieved chunk before generation (Corrective RAG) so the agent's autonomous retrieval decisions can't bypass the trust/hallucination checks a regulated or clinical context requires.", "conf": "high"}
    if s["agentic"]:
        return {"name": RAG_TYPES[5], "why": "Agentic workflow — let the agent decide dynamically when to retrieve and from which source, rather than always retrieving.", "conf": "high"}
    if s["enterprise"] and s["knowledgeBase"]:
        return {"name": RAG_TYPES[4], "why": "Enterprise knowledge spans many interlinked systems (Confluence, Jira, Drive) — a knowledge-graph layer improves cross-document reasoning over flat vector search.", "conf": "high"}
    if s["compliance"] or s["healthcare"]:
        return {"name": RAG_TYPES[6], "why": "Compliance/clinical context demands high answer trust — Corrective RAG validates retrieved chunks before generation to reduce hallucination risk.", "conf": "high"}
    if s["dataHeavy"]:
        return {"name": RAG_TYPES[2], "why": "Mixing keyword and vector search improves recall across large, heterogeneous document sets typical of data-heavy orgs.", "conf": "medium"}
    return {"name": RAG_TYPES[1], "why": "A solid general-purpose default: retrieve broadly, then rerank for relevance before feeding the LLM — better quality than naive top-k RAG with modest added complexity.", "conf": "low"}


def pick_guardrails(s):
    g = ["Input/output content filtering (toxicity, PII leakage)"]
    if s["compliance"] or s["healthcare"] or s["finance"]:
        g.append("PII/PHI redaction & data-loss-prevention layer")
    g.append("Prompt-injection & jailbreak defense")
    if s["ragNeed"] or s["chatbot"]:
        g.append("Hallucination / groundedness checking against retrieved sources")
    if s["voice"]:
        g.append("Voice-channel safety: ASR-misrecognition tolerance and re-confirmation before high-risk actions taken from spoken input")
    if s["agentic"]:
        g.append("Human-in-the-loop approval for high-risk agent actions")
        g.append("Agent identity as a first-class RBAC concern: scope each agent to minimal permissions, make its access time-bound (JIT, not standing), log every action taken, and keep a revocation path — govern it with the same rigor as a human account (see IAM Options section)")
    g.append("Rate limiting & abuse/cost-control monitoring")
    if s["compliance"]:
        g.append("Audit logging of all prompts/responses for compliance review")
    return g


def pick_cicd(s):
    # Team-skill picks the actual CI platform name (a real, interchangeable choice) rather than
    # always defaulting to GitHub Actions — same "matching skills beats a theoretically-better
    # pick" rule as the rest of this feature. Checked in a fixed order since a team realistically
    # names one primary CI tool; falls back to GitHub Actions absent any explicit match.
    ci, ci_skill_hit = "GitHub Actions", False
    if s["jenkinsMentioned"]:
        ci, ci_skill_hit = "Jenkins", True
    elif s["gitlabCiMentioned"]:
        ci, ci_skill_hit = "GitLab CI", True
    elif s["circleciMentioned"]:
        ci, ci_skill_hit = "CircleCI", True
    elif s["azureDevopsMentioned"]:
        ci, ci_skill_hit = "Azure DevOps Pipelines", True
    elif s["githubActionsMentioned"]:
        ci_skill_hit = True

    def skill_note(v):
        # Only the tools the requirement shows OWNERSHIP of earn the "already knows" bonus.
        k = s.get("known") or {}
        known_ci = ci_skill_hit and (k.get("jenkins") or k.get("gitlabCi") or k.get("circleci")
                                     or k.get("azureDevops") or k.get("githubActions"))
        known = [n for n in [known_ci and ci, k.get("terraform") and "Terraform"] if n]
        if not known:
            return v
        return {"v": v["v"],
                "why": v["why"] + f" Bonus: your team already knows {' and '.join(known)}, so this "
                                  "isn't just the balanced default — it matches existing skills too.",
                "conf": "high" if v["conf"] == "high" else "medium"}

    if s["onPrem"]:
        # Air-gapped runners must be self-hosted regardless — but still honor a named team-known
        # tool over the generic "GitLab CE or Jenkins either-or" phrasing when one was stated.
        on_prem_ci = "Jenkins" if s["jenkinsMentioned"] else "GitLab CE" if s["gitlabCiMentioned"] else "GitLab CE or Jenkins"
        return {"v": f"Self-hosted {on_prem_ci} with self-hosted runners, deploying via Terraform to your private infrastructure", "why": "Cloud-hosted CI/CD (GitHub Actions cloud runners, Vercel) needs internet connectivity to reach your infrastructure — an air-gapped environment needs the entire pipeline, including runners, inside the network boundary.", "conf": "high"}
    if s["huaweiShop"]:
        return skill_note({"v": "Huawei Cloud CodeArts (Pipeline, Build, Deploy) → CCE, Resource Template Service (RTS) for infra-as-code", "why": "Explicit Huawei Cloud usage detected — CodeArts is Huawei's native CI/CD suite (covers what GitHub Actions/Jenkins + Terraform would do, in one integrated toolchain), matching your existing cloud footprint.", "conf": "high"})
    if s["minimalProject"] and not s["enterprise"]:
        return {"v": "Your PaaS's auto-deploy on git push — no separate CI/CD pipeline, no Terraform", "why": "Terraform-driven infrastructure-as-code and a multi-stage deploy pipeline exist to make infrastructure changes reviewable and repeatable across environments — a single free-tier PaaS deployment has no infrastructure to manage and typically no second environment. Pushing to your main branch and letting the platform auto-deploy is the entire pipeline you need; add a GitHub Actions step to run tests before deploy once you have tests worth gating on.", "conf": "high"}
    if s["startupMvp"]:
        return skill_note({"v": f"{ci} → Vercel (frontend) + Cloud Run/Fargate (backend)", "why": "Fastest path to production for a small team, minimal infra to manage.", "conf": "high"})
    if s["enterprise"]:
        return skill_note({"v": f"{ci} → ArgoCD (GitOps) → Kubernetes, Terraform for infra-as-code", "why": "GitOps gives auditable, repeatable deployments at enterprise scale with multiple environments/teams.", "conf": "high"})
    return skill_note({"v": f"{ci} → Terraform + Kubernetes (or Vercel for frontend-only pieces)", "why": "Balanced CI/CD with infra-as-code as the team and service count grow.", "conf": "low"})


def pick_dns(s):
    if s["onPrem"]:
        return {"v": "Internal DNS (BIND / Windows DNS / private zone) — no public DNS provider", "conf": "high"}
    if s["awsShop"]:
        return {"v": "Route 53 (AWS-native, integrates with ALB/CloudFront)", "conf": "high"}
    if s["huaweiShop"]:
        return {"v": "Huawei Cloud DNS (native, integrates with ELB and CDN)", "conf": "high"}
    return {"v": "Cloudflare DNS (fast propagation, built-in DDoS/WAF) — or Route 53 if fully AWS-native", "conf": "low"}


def pick_docs(s):
    return [
        {"label": "C4 Model", "text": "Context & Container diagrams for stakeholder alignment; Component diagrams per service."},
        {"label": "HLD", "text": "High-level design: system boundaries, major components, data flow, tech choices & rationale (this page is a first draft input)."},
        {"label": "LLD", "text": "Low-level design per service: API contracts, DB schemas, sequence diagrams, error handling."},
        {"label": "ADRs", "text": "Architecture Decision Records for each major choice above — capture context, decision, consequences."},
    ]


# ---------- AI model serving & integration architecture ----------


def pick_model_orchestration(s):
    mapping = [
        {"task": "Reasoning agent — architecture/system design & complex multi-step reasoning", "model": "Frontier large model (Claude Opus/Sonnet, GPT-5/o-series, Gemini Pro)", "why": "These calls are low-volume and high-stakes — the cost premium is trivial against the value of a correct design decision, and deep reasoning quality drops off fastest on smaller models.", "runtimeHint": "Cloud API / OpenRouter — quality-critical, low-volume; not worth self-hosting."},
        {"task": "Code agent — generation, review & refactoring", "model": "Mid-large code-tuned model (Claude Sonnet, GPT-4.1-class, DeepSeek-Coder-V2, Codestral)", "why": "Strong code benchmarks at meaningfully lower cost/latency than reserving your top-tier reasoning model for every completion.", "runtimeHint": "Cloud API — code is the most quantization/downgrade-sensitive task type, avoid the on-device/small-model tier for this one."},
        {"task": "Summarization agent — document/thread condensation", "model": "Mid-size model, 12B–30B (or a 4B–12B open-weight model for short/simple inputs)", "why": "Summarization is more forgiving than code or agentic tool-use — a well-tuned mid-size (or even small) model does this reliably, so it's one of the better candidates for cost/latency optimization via a smaller model.", "runtimeHint": "Good Ollama/self-host candidate if volume is steady — one of the cheapest tasks to run locally without a quality hit."},
        {"task": "Classification, extraction, routing, simple chat", "model": "Small open-weight model, 4B–12B (Gemma, Llama, DeepSeek-small, Phi)", "why": "High call volume, low per-call complexity — this is where model cost dominates total spend, so the cheapest model that clears the quality bar wins. Also the tier most worth self-hosting.", "runtimeHint": "Best Ollama/self-host candidate — high volume + low complexity is exactly where dedicating hardware pays off fastest."},
        {"task": "RAG answer synthesis", "model": "Mid-size model, 12B–30B", "why": "Needs enough reasoning capacity to stay grounded in retrieved context without hallucinating, but doesn't need frontier-level general reasoning.", "runtimeHint": "Self-hostable at steady volume; cloud API/OpenRouter otherwise for simplicity."},
        {"task": "Agent orchestration / multi-step tool-use", "model": "Frontier or a tool-use-specialized large model", "why": "Reliability of tool-call formatting and multi-step planning degrades noticeably on smaller models — this is the task type least tolerant of downgrading.", "runtimeHint": "Cloud API — tool-call reliability is the task type least tolerant of a smaller/local model."},
    ]
    if s["startupMvp"] and s["smallTeam"] and not s["agentic"] and not s["highScale"]:
        return {
            "strategy": "Single model to start",
            "why": "A small team at low, unpredictable volume gets more value from operational simplicity (one API, one bill, no routing logic to build/maintain) than from cost optimization that doesn't matter yet at your call volume. Pick one capable mid/frontier-tier model and use it for everything.",
            "when": "Split into multiple models the moment any one task type becomes high-volume enough that its API cost is visible on your bill, or you add an agentic/tool-use workflow that a general chat model handles unreliably.",
            "mapping": mapping, "conf": "high",
        }
    return {
        "strategy": "Multiple models, routed by task",
        "why": "Your requirements span reasoning-heavy, code, and/or high-volume simple tasks — using one model (almost always the most expensive one, by default) for all of them means overpaying for the easy calls or underpowering the hard ones. Route by task using the mapping below.",
        "when": "Consolidate back to a single model only if orchestration/routing complexity starts costing more engineering time than the routing saves in inference spend — this crossover mostly hits very small teams.",
        "mapping": mapping, "conf": "high" if s["agentic"] else "medium",
    }


def pick_hosting_location(s):
    if s["onPrem"]:
        return {
            "rec": "Local / self-hosted only — no cloud API calls of any kind",
            "why": "Air-gapped/on-prem means there is no path to the public internet at all, so cloud LLM APIs (Anthropic, OpenAI, etc.) are unreachable regardless of data sensitivity — every model has to run inside your network boundary.",
            "budgetNote": "Budget for real GPU hardware and the staff to operate it — this is a fixed requirement at any data-sensitivity level once you're genuinely air-gapped, not an optional cost optimization.",
            "securityNote": "", "when": "", "conf": "high",
        }
    sensitive = s["compliance"] or s["healthcare"] or (s["security"] and s["finance"])
    if sensitive:
        return {
            "rec": "Local / self-hosted (VPC-isolated) for anything touching regulated or sensitive data; cloud API allowed for non-sensitive auxiliary tasks",
            "why": "Compliance/healthcare/security signals mean data residency and auditability outweigh convenience — self-hosting an open-weight model inside your own VPC (or on-prem) means prompts and outputs never leave your security boundary. This is a hybrid posture, not all-or-nothing: low-risk tasks (e.g. formatting, non-PII classification) can still use cloud APIs.",
            "budgetNote": "Upfront GPU cost is real, but for regulated workloads it's usually a compliance requirement, not a cost optimization — treat it as a fixed cost of being in this market, not an optional line item.",
            "securityNote": "Confirm your cloud API providers' data-retention and training-use policies even for the non-sensitive path — \"enterprise\" tiers from major LLM vendors typically opt out of training on your data, but verify per-vendor.",
            "conf": "high",
        }
    if s["startupMvp"] and not s["highScale"]:
        return {
            "rec": "Cloud API (hosted, pay-per-token)",
            "why": "No infra to operate or GPUs to amortize, and pay-per-use pricing matches a small team's unpredictable early-stage volume. Self-hosting only pays off once you have enough constant, predictable request volume to keep a GPU meaningfully utilized around the clock — below that threshold, idle GPU time makes self-hosting more expensive than API calls, not less.",
            "when": "Revisit self-hosting once a specific high-volume, low-complexity task (e.g. classification/extraction) is running constantly enough that a single small-model GPU would sit near capacity — that's the crossover point, not overall company scale.",
            "conf": "high",
        }
    return {
        "rec": "Hybrid: cloud API as the default, local/self-hosted for your highest-volume, most predictable small-model workload",
        "why": "At real scale, a small fraction of your call volume (usually classification/extraction/routing) accounts for a large fraction of total request count. Self-hosting just that workload on a right-sized GPU, while keeping variable/bursty/complex-reasoning traffic on cloud APIs, captures most of the cost benefit without taking on full self-hosting operational risk for everything.",
        "budgetNote": "Rule of thumb: self-hosting a 4B–12B model becomes cost-competitive with cloud API pricing once you're sustaining enough request volume to keep one GPU above roughly 40–50% utilization continuously — model this against your actual projected volume before committing capital.",
        "securityNote": "", "conf": "medium",
    }


COMPUTE_TIER_TABLE = [
    {"tier": "Mobile / Tablet", "ram": "4–16 GB unified", "modelFit": "1B–4B at Q4_K_M (4-bit)", "examples": "iPhone/Android flagship, iPad Pro", "notes": "On-device inference runs on the device's own RAM/CPU/NPU — no dedicated GPU. See the on-device runtime note below for framework choice (llama.cpp/GGUF, MLC-LLM, ExecuTorch)."},
    {"tier": "Laptop (Windows / Mac)", "ram": "16–36 GB unified/system RAM", "modelFit": "7B–14B at Q4_K_M/Q5_K_M", "examples": "MacBook Pro/Air (M-series), Windows laptop with 32GB+ RAM", "notes": "The natural tier for local dev work and Ollama-based prototyping — comfortable single-user inference, not concurrent-request production serving."},
    {"tier": "Workstation / Studio-class", "ram": "96–256 GB unified memory", "modelFit": "30B–70B comfortably; up to ~200B (inference) on DGX Spark, ~405B across 2 linked DGX Spark units", "examples": "Mac Studio (M3 Ultra, 96–512GB unified), NVIDIA DGX Spark (128GB unified, Grace Blackwell)", "notes": "DGX Spark is explicitly positioned as a desktop dev/prototyping box for local agents, not a production server — same caveat applies to Mac Studio for anything needing concurrent multi-user serving."},
    {"tier": "Server (dedicated GPU)", "ram": "24–80 GB VRAM per GPU", "modelFit": "4B–70B depending on GPU count/size, int4 quantized", "examples": "Single/multi RTX 4090, L4, A100, or H100", "notes": "Where production self-hosted serving actually happens — dedicated VRAM instead of unified memory shared with the OS, and built for concurrent request throughput."},
    {"tier": "Enterprise server / datacenter", "ram": "Multi-GPU cluster (4–8+ H100/H200, 320GB+ aggregate VRAM)", "modelFit": "70B–400B+, distributed/tensor-parallel serving", "examples": "On-prem GPU cluster, or cloud-hosted GPU fleet (AWS/GCP/Azure)", "notes": "This is usually also the point where a frontier cloud API (Claude, GPT, Gemini) wins on total cost of ownership versus self-hosting at this scale — self-host here only for a hard data-residency/compliance reason, not for cost."},
]


def pick_compute_tier(s):
    if s["mobile"] or s["iot"] or s["tablet"]:
        return {"tier": "Mobile / Tablet", "why": "On-device inference target detected (mobile/tablet/IoT-gateway) — this is a fundamentally different sizing question from server hosting: RAM shared with the OS, no dedicated GPU, battery/thermal limits. Start at the 1B–4B tier and size up only if the smallest model that clears your quality bar isn't sufficient."}
    if (s["compliance"] or s["healthcare"] or s["security"]) and s["enterprise"]:
        return {"tier": "Server (dedicated GPU)", "why": "Fully local deployment for regulated data needs enough dedicated VRAM to approach cloud-frontier quality at the 30B tier without the added complexity of multi-GPU distributed serving — move to the Enterprise tier only once request volume genuinely requires it."}
    if s["enterprise"] and s["highScale"]:
        return {"tier": "Enterprise server / datacenter", "why": "Enterprise scale plus high request volume is where dedicated multi-GPU capacity (or an equivalent cloud GPU fleet) becomes worth the operational complexity — though re-check against a frontier cloud API's total cost first, since this tier is exactly where API pricing often still wins."}
    if s["startupMvp"] or s["smallTeam"]:
        return {"tier": "Laptop (Windows / Mac)", "why": "A small team's realistic self-hosting starting point is local dev-machine inference (Ollama on a laptop) for prototyping — not a dedicated GPU server, which is premature spend before you have predictable production volume."}
    return {"tier": "Server (dedicated GPU)", "why": "Default mid-scale assumption absent a stronger signal either way — a single dedicated GPU (int4-quantized 4B–12B model) is the realistic production tier once you're past laptop-scale prototyping but before enterprise multi-GPU need."}


def pick_runtime(s):
    sensitive = s["compliance"] or s["healthcare"] or s["security"] or (s["security"] and s["finance"])
    if s["onPrem"]:
        return {"rec": "Ollama (fully local, no external network calls)", "why": "Air-gapped/no-public-cloud rules out any router or API that proxies requests to third-party infrastructure — Ollama running entirely inside your network boundary is the only option that fits, not a preference.", "conf": "high"}
    if sensitive and s["selfHostInfra"]:
        return {"rec": "Ollama, self-hosted alongside your existing Docker/Kubernetes infrastructure", "why": "You already carry the ops burden of self-hosting (Docker/K8s in the stack) and have sensitive-data handling requirements — Ollama keeps prompts/outputs on infrastructure you already operate and control, rather than adding a new third-party data-processing relationship for a marginal convenience gain.", "conf": "high"}
    if sensitive:
        return {"rec": "Ollama (self-hosted) for anything touching regulated/sensitive data; direct provider SDK for the rest", "why": "Compliance/security-sensitive data shouldn't transit a third-party router even one that claims not to log content — Ollama keeps it on infrastructure you control. Non-sensitive auxiliary tasks can still use a direct cloud provider SDK without adding OpenRouter's extra hop for something that doesn't need model-routing flexibility.", "conf": "high"}
    if s["startupMvp"] and not s["selfHostInfra"]:
        return {"rec": "OpenRouter (or a direct provider SDK if you only ever need one model family)", "why": "A small team without existing GPU/self-hosting infrastructure gets model breadth (300+ models across many providers via one API) and zero hardware ownership from OpenRouter — the ~5.5% routing fee and per-token pricing is a reasonable trade for not operating GPUs at your stage. Revisit Ollama once you have steady, predictable request volume worth dedicating hardware to.", "conf": "medium"}
    if s["selfHostInfra"] and (s["highScale"] or s["enterprise"]):
        return {"rec": "Hybrid: Ollama for your steady, predictable high-volume workload; OpenRouter (or direct SDK) for bursty/exploratory traffic", "why": "This is the common production pattern, not a compromise — steady, high-volume request classes (the ones worth dedicating a GPU to) run cheaper and more privately on self-hosted Ollama, while unpredictable or exploratory traffic is better served by not pre-committing hardware to it. Route by workload predictability, not an all-or-nothing platform choice.", "conf": "medium"}
    return {"rec": "Direct provider SDK to start; move to OpenRouter if you need multi-model flexibility, or Ollama once self-hosting infrastructure and steady volume both exist", "why": "Absent a specific driver (data sensitivity, existing self-host infra, or a concrete need for many model families at once), the simplest option — calling your chosen provider's SDK directly — has the least moving parts. Add OpenRouter's routing layer or Ollama's self-hosting only when a concrete requirement calls for it.", "conf": "low"}


def pick_interface_topology(s):
    hosting = pick_hosting_location(s)
    glossary = "Hybrid = one gateway routing requests across local + cloud models by cost/security/task. Distributed = multiple independent serving replicas (often regional) behind a load balancer, for scale/availability, not policy. Mesh = service-mesh-style interconnection (Istio-class) giving consistent routing, retries, and observability across many AI services/agents talking to each other and to models."

    if s["onPrem"]:
        llm = {"rec": "Local-only interface (single self-hosted model, no external routing)", "why": "Air-gapped/no-public-cloud means there is no cloud model to route to at all — this isn't a hybrid or distributed topology decision, it's a single local serving endpoint inside your network boundary. A \"hybrid\" gateway implies routing to a cloud backend that, by requirement, doesn't exist here."}
    elif (s["compliance"] or s["security"]) and (s["enterprise"] or s["highScale"]) and s["agentic"]:
        llm = {"rec": "Mesh interface", "why": "Many services/agents, regulated data, and real scale together mean you need consistent mTLS, retry policy, and observability applied uniformly across every AI and non-AI service call — the same reasoning that justifies Istio for your general architecture applies to AI traffic specifically. Layer it on top of the service mesh you're already running, don't stand up a separate one."}
    elif hosting["rec"].startswith("Hybrid") or hosting["rec"].startswith("Local"):
        llm = {"rec": "Hybrid interface", "why": "You're already routing between local and cloud models for cost/security reasons — put a unified LLM gateway (LiteLLM/OpenRouter-style abstraction) in front of both so application code calls one interface and the gateway handles which backend serves each request."}
    elif s["highScale"] or s["globalMultiRegion"]:
        llm = {"rec": "Distributed interface", "why": "Your need is scale and regional latency, not policy routing between different model types — multiple regional serving replicas behind a load balancer solves that directly without the added complexity of a full gateway/mesh layer."}
    else:
        llm = {"rec": "Direct integration (single provider SDK)", "why": "At your current scope, a routing/mesh layer is complexity you don't need yet — call your chosen model provider's SDK directly and revisit once you add a second model, hosting location, or region."}

    if s["onPrem"]:
        rag = {"rec": "Direct integration (single self-hosted retrieval service)", "why": "No cloud connectivity exists in an air-gapped environment, so retrieval must be one self-hosted vector store/service entirely inside your network boundary — not a hybrid or distributed setup that assumes cloud reachability."}
    elif s["enterprise"] and s["knowledgeBase"]:
        rag = {"rec": "Hybrid interface (local + cloud vector search, or multiple source-specific retrievers behind one router)", "why": "Enterprise knowledge usually spans multiple systems (Confluence, Drive, internal DBs) — a hybrid retrieval router lets each source use its best-fit storage/search while presenting one retrieval interface to the LLM layer."}
    elif s["highScale"] and s["globalMultiRegion"]:
        rag = {"rec": "Distributed interface (sharded/replicated vector index across regions)", "why": "Query latency and index size at global scale usually force sharding or regional replication of the vector index well before any policy-routing need arises."}
    elif s["agentic"] and s["enterprise"]:
        rag = {"rec": "Mesh interface (multiple independent RAG services behind consistent mesh policy)", "why": "Multiple agents each needing governed, observable access to different knowledge sources is the same problem service mesh solves for microservices generally — apply it to your retrieval services too."}
    else:
        rag = {"rec": "Direct integration (single retrieval service)", "why": "One vector store, one retrieval service, called directly — no need for extra topology until you have multiple knowledge sources or regions to reconcile."}

    if not s["agentic"]:
        agent = {"rec": "Not applicable — no multi-agent/agentic workflow detected", "why": "This axis only matters once you have more than one agent or a genuinely autonomous multi-step workflow to coordinate. A single request/response LLM call doesn't need an agent topology decision."}
    elif s["onPrem"]:
        agent = {"rec": "Local-only orchestration (single self-hosted orchestrator process)", "why": "Same constraint as the LLM layer — no external network path exists, so agent coordination has to run entirely inside your boundary rather than routing to any external agent/model service."}
    elif (s["compliance"] or s["security"]) and s["enterprise"]:
        agent = {"rec": "Mesh interface (agents as first-class mesh participants)", "why": "Multiple agents each calling different tools/models/data sources in a regulated context need the same consistent mTLS, retry, and audit-observability policy your service mesh already gives regular services — treat agent-to-agent and agent-to-tool calls as mesh traffic, not an unmanaged side channel."}
    elif s["highScale"] or s["globalMultiRegion"]:
        agent = {"rec": "Distributed orchestration (multiple independent agent-runner replicas behind a queue/load balancer)", "why": "At real scale, a single orchestrator process becomes the bottleneck and single point of failure — run multiple stateless agent-runner replicas pulling from a shared task queue, the same pattern as any other horizontally-scaled service."}
    elif s["selfHostInfra"] or hosting["rec"].startswith("Hybrid") or hosting["rec"].startswith("Local"):
        agent = {"rec": "Hybrid orchestration (one coordinator routing sub-tasks to local or cloud models by task type)", "why": "You're already splitting model calls between local and cloud (see the runtime recommendation above) — the agent orchestrator should make that same routing decision per sub-task: a reasoning-heavy step goes to a frontier cloud model, a classification/extraction step can route to your self-hosted small model."}
    else:
        agent = {"rec": "Direct orchestration (single coordinator process, no distribution layer yet)", "why": "One agentic workflow, one coordinator calling out to tools/models directly — add distribution or mesh complexity only once you have multiple concurrent agent workflows or a scale/compliance driver for it."}

    return {"glossary": glossary, "llm": llm, "rag": rag, "agent": agent}


def pick_mcp_vs_api(s):
    if s["agentic"] or s["enterprise"]:
        return {
            "rec": "MCP (Model Context Protocol) server",
            "why": "MCP standardizes tool discovery, schemas, and context handoff so any MCP-compatible client (Claude Desktop, Claude Code, other agents) can use the same tool without bespoke integration work per client. That reuse value compounds fast once more than one agent or team needs the same internal capability — which agentic and enterprise contexts both imply.",
            "when": "A raw API call is still the right choice for a single, simple, one-off integration where no other agent/client will ever need to reuse it, or for ultra-low-latency internal calls where MCP's JSON-RPC layer adds overhead you can't afford.",
            "conf": "high",
        }
    return {
        "rec": "Direct API calls are fine for now; wrap as MCP once a second consumer appears",
        "why": "With a single application and no agentic tool-use pattern yet, a direct API integration is simpler to build and debug than standing up an MCP server for one caller.",
        "when": "Move to MCP the moment a second AI agent, internal team, or client (e.g. Claude Desktop/Code) needs to call the same capability — that's the point where standardized discovery and reuse start paying for the extra layer.",
        "conf": "medium",
    }


def pick_guardrail_pipeline(s):
    stages = [
        {"stage": "1. Input", "desc": "Validate and sanitize the raw user request: content filtering, prompt-injection pattern detection, PII/PHI detection, rate limiting before it ever reaches a model."},
        {"stage": "2. Retrieval / tool-call", "desc": "Check retrieved documents for relevance/groundedness before they're added to context (this is what Corrective/Self-RAG do); validate tool-call arguments against schema and permissions before execution." if (s["ragNeed"] or s["knowledgeBase"]) else "Validate any tool-call arguments against schema and permissions before execution — skip if no retrieval/tools are in play."},
        {"stage": "3. Generation (in-flight)", "desc": "Stream-time moderation on partial output where latency allows, so a policy-violating response can be halted before it fully renders to the user rather than only caught after the fact."},
        {"stage": "4. Output", "desc": "Final check on the complete response: toxicity/safety filtering, PII leakage scan, groundedness/citation check against retrieved sources, format/schema validation for structured outputs."},
        {"stage": "5. Post-hoc evals & monitoring (offline)", "desc": "You can't eval every request at your volume — run continuous sampled evals (LLM-as-judge plus periodic human review) on a statistically meaningful slice, track drift over time, and gate model/prompt changes behind regression evals before rollout." if s["highScale"] else "Run sampled evals (LLM-as-judge plus periodic human review) on a slice of production traffic, and gate any model/prompt change behind a regression eval suite before rollout."},
    ]
    return {"stages": stages, "verdict": "Guardrails belong at every stage above, not just input/output — IO-only filtering catches the obvious cases but misses retrieval-stage hallucination sources and mid-generation policy violations that only in-flight or retrieval-stage checks can catch."}


def pick_vector_db_placement(s, rag_result):
    no_rag_needed = rag_result["name"] == "RAG likely not required"
    structured_rag = bool(rag_result.get("name")) and rag_result["name"].startswith("Structured/SQL")
    if no_rag_needed:
        return {"needed": False, "where": "", "dbChoice": "", "why": "No knowledge-base/document-retrieval need was detected, so there's nothing for a vector database to index — skip it. Add one later if you introduce a \"search our docs/data\" feature."}
    if structured_rag:
        return {"needed": False, "where": "", "dbChoice": "", "why": "Your retrieval need is over structured/relational data — that's served by querying your existing database (text-to-SQL or schema-aware retrieval), not a vector index. A vector DB would be the wrong tool here."}

    if not s["dataHeavy"] and not s["enterprise"] and not s["highScale"]:
        db_choice = "pgvector extension on your existing PostgreSQL instance"
    elif s["unstructured"] and not s["structured"]:
        db_choice = "A dedicated vector database (Qdrant, Weaviate, or Milvus) — or Pinecone if you prefer fully managed"
    else:
        db_choice = "MongoDB Atlas Vector Search (if MongoDB is already your document store) or a dedicated vector DB (Qdrant/Weaviate/Milvus/Pinecone) if you need hybrid search and metadata filtering at scale"

    why = (
        "At your current scale, adding pgvector to a database you already operate avoids introducing an entirely new system to run, back up, and monitor. Migrate to a dedicated vector DB once query volume or index size makes pgvector's performance a bottleneck."
        if (not s["dataHeavy"] and not s["enterprise"] and not s["highScale"])
        else "At your scale, a purpose-built vector database gives you approximate-nearest-neighbor performance, hybrid (keyword + vector) search, and metadata filtering that general-purpose databases only support with real caveats."
    )
    return {
        "needed": True,
        "where": "It sits in the retrieval path, parallel to (not instead of) your primary database: an offline ingestion pipeline chunks and embeds your source documents and upserts them into the vector store ahead of time; at query time, the user's query is embedded and matched against that store to retrieve relevant chunks, which are then injected into the LLM's context before generation.",
        "dbChoice": db_choice, "why": why,
    }


# ---------- Head-to-head trade-off decisions (why + when to switch) ----------


def pick_tradeoffs(s):
    t = []

    # 0/1. On-prem overrides cloud strategy; else single-cloud vs multi-cloud
    if s["onPrem"]:
        t.append({"d": "Public cloud vs. On-premises", "rec": "On-premises / air-gapped private infrastructure", "why": "An explicit no-public-cloud / air-gapped requirement overrides the usual cloud trade-off entirely — this isn't a single-vs-multi-cloud decision, it's a build-and-operate-your-own-infrastructure decision.", "when": "Revisit only if the air-gap/no-public-cloud constraint is ever relaxed (e.g. a sovereign/government cloud region becomes an approved option).", "conf": "high"})
    elif s["enterprise"] and s["globalMultiRegion"] and s["compliance"]:
        t.append({"d": "Single-cloud vs. Multi-cloud", "rec": "Primary cloud + a scoped secondary cloud (DR / regulatory only)", "why": "Global, regulated, enterprise-scale profile — data-residency law or contractual disaster-recovery requirements often force a second cloud presence, but that's different from running everything active-active across two clouds.", "when": "Go further into full multi-cloud only if you have multiple regions with hard data-sovereignty laws requiring in-country cloud presence, or a board-level mandate to avoid single-vendor concentration risk regardless of cost.", "conf": "medium"})
    else:
        t.append({"d": "Single-cloud vs. Multi-cloud", "rec": "Single cloud", "why": "Multi-cloud roughly doubles operational complexity — two IAM models, two networking stacks, two sets of managed services to learn and monitor — for a benefit (vendor leverage, avoiding lock-in) that rarely pays off before significant scale.", "when": "Reconsider if a single-vendor outage has caused a business-critical incident more than once, procurement specifically wants renewal leverage, or compliance mandates in-country presence your primary cloud can't offer.", "conf": "high"})

    # 2. IaC tool (OpenTofu-aware)
    if s["pythonMentioned"] and not s["awsShop"]:
        t.append({"d": "OpenTofu/Terraform vs. Pulumi vs. native IaC", "rec": "OpenTofu (or Terraform) as the default, with Pulumi as a strong alternative given your Python usage", "why": "HCL-style declarative IaC remains the safest default for module ecosystem size, cloud-agnostic multi-cloud optionality, and ease of hiring — but since HashiCorp relicensed Terraform to BSL in 2023, OpenTofu (the Linux Foundation-governed, MPL-2.0/OSI-approved fork) is now the version worth defaulting to for a genuinely open, vendor-neutral toolchain; the two stayed compatible enough that switching later is mostly mechanical. Pulumi is worth it specifically because it lets your existing Python team write infra in a real language (loops, conditionals, unit tests) instead of HCL.", "when": "Pick Pulumi over OpenTofu/Terraform if your team already writes Python/TypeScript daily and wants infra code reviewed and tested the same way as application code. Stay on HashiCorp Terraform specifically only if you depend on HCP Terraform Stacks or a vendor-consolidation/procurement requirement mandates HashiCorp as sole vendor. Pick cloud-native IaC (CDK, Bicep, Deployment Manager) only if you are firmly single-cloud and want zero third-party tooling in the deploy path.", "conf": "medium"})
    elif s["awsShop"] and s["startupMvp"]:
        t.append({"d": "OpenTofu/Terraform vs. AWS CDK vs. native IaC", "rec": "OpenTofu (or Terraform) as the default; AWS CDK is a reasonable alternative for an AWS-only small team", "why": "OpenTofu/Terraform is cloud-agnostic and keeps optionality if you ever add a second cloud or need to hire from the broader IaC talent pool — OpenTofu specifically over HashiCorp's Terraform build for its OSI-approved MPL-2.0 license (Terraform moved to BSL in 2023) and growing adoption momentum, unless a specific reason ties you to HashiCorp's build. CDK gives tighter day-one AWS service coverage and lets you write infra in TypeScript/Python, at the cost of being AWS-only.", "when": "Choose CDK specifically if you're confident you'll stay AWS-only long-term and want less HCL to learn. Move to OpenTofu/Terraform (or add it) the moment a second cloud or an IaC-experienced hire enters the picture.", "conf": "medium"})
    else:
        t.append({"d": "OpenTofu vs. Terraform vs. other IaC", "rec": "OpenTofu", "why": "Industry-standard, cloud-agnostic, declarative IaC with the largest module ecosystem and community support — the safest long-term default for hiring, documentation, and multi-cloud optionality. Specifically OpenTofu over HashiCorp's own Terraform build: after HashiCorp relicensed Terraform to the Business Source License in 2023 (not OSI-approved, restricts competing commercial use), the Linux Foundation-backed OpenTofu fork kept the original MPL-2.0 open-source license, has since shipped independent improvements (built-in state encryption, provider for_each, an -exclude flag), and had passed HashiCorp's own Terraform in share of new workspace creation on at least one major TACOS platform by mid-2026. The CLI and provider ecosystem stayed compatible enough that switching between them later is a mostly mechanical migration, not a rewrite.", "when": "Stay on HashiCorp's Terraform build specifically if you depend on HCP Terraform Stacks (no OpenTofu equivalent yet) or a procurement/vendor-consolidation requirement mandates HashiCorp as sole vendor. Reconsider the whole category if your team is deeply invested in a general-purpose language (Python/TypeScript/Go) and wants Pulumi's programmatic style, or you are permanently single-cloud and want to drop third-party tooling in favor of native IaC (CloudFormation/Bicep/Deployment Manager).", "conf": "medium"})

    # 3. Kafka vs Pub/Sub vs managed queue
    if s["highScale"] or s["realtime"] or s["finance"]:
        t.append({"d": "Kafka vs. Pub/Sub vs. managed queue (SQS/SNS)", "rec": "Kafka", "why": "You need a durable, replayable log — required for audit trails, fraud/analytics pipelines, high sustained throughput, or multiple independent consumer groups reading the same stream at different speeds. Managed queues don't give you replay or that throughput ceiling.", "when": "Downgrade to a managed queue (SQS/Pub/Sub) if it turns out you don't actually need replay/audit history and traffic is moderate — Kafka's operational cost (self-managed or Confluent/MSK bill) only pays off once you're using its durability and replay guarantees.", "conf": "high"})
    elif s["gcpShop"]:
        t.append({"d": "Kafka vs. Pub/Sub vs. managed queue (SQS/SNS)", "rec": "Google Pub/Sub", "why": "Fully managed, zero ops, integrates natively with the rest of a GCP stack. The right choice when you don't yet have Kafka-specific needs like event replay, ultra-high sustained throughput, or complex multi-consumer-group patterns.", "when": "Move to Kafka (Confluent Cloud or self-managed on GKE) once you need event replay for audit, multiple independent consumer groups at different read speeds, or throughput/latency Pub/Sub can't guarantee at your scale.", "conf": "high"})
    else:
        t.append({"d": "Kafka vs. Pub/Sub vs. managed queue (SQS/SNS)", "rec": "Managed queue (SQS/Pub/Sub) first; adopt Kafka only when you outgrow it", "why": "Start with the lowest-ops option. Introducing a Kafka cluster before you actually need its guarantees just adds infrastructure to operate for no measurable benefit.", "when": "Move to Kafka when you need: event replay/audit trail, multiple consumer groups reading the same stream at different speeds, sustained throughput above roughly 10k messages/sec, or you're building a real event-sourcing/CDC pipeline.", "conf": "medium"})

    # 4. Kubernetes vs Serverless — mirrors pick_compute()'s branch order exactly
    if (s["startupMvp"] or s["smallTeam"]) and (s["highScale"] or s["enterprise"] or s["realtime"]):
        t.append({"d": "Kubernetes vs. Serverless", "rec": "Serverless containers (Cloud Run / Fargate) — middle path", "why": "Small team and real-time/high-scale/enterprise needs pull in different directions: full self-managed Kubernetes is more operational overhead than your team can likely absorb, but plain serverless functions under-deliver on control at this scale. Managed serverless containers give autoscaling and container-level control without a Kubernetes control plane to operate.", "when": "Move to full self-managed Kubernetes once you have dedicated platform engineering capacity; fall back to plain serverless functions if scale/latency needs turn out lighter than described.", "conf": "medium"})
    elif s["startupMvp"] or (s["smallTeam"] and not s["highScale"]):
        t.append({"d": "Kubernetes vs. Serverless", "rec": "Serverless (Cloud Run / Lambda / Cloud Functions)", "why": "No cluster to operate, patch, or right-size; you pay only for what you use, which matches a small team's time budget and an early-stage product's unpredictable traffic.", "when": "Move to Kubernetes once you have many services with complex inter-service networking needs, need fine-grained resource/cost control at steady high load, or serverless cold-start latency becomes a measurable user-facing problem.", "conf": "high"})
    elif s["highScale"] or s["enterprise"] or s["realtime"]:
        t.append({"d": "Kubernetes vs. Serverless", "rec": "Kubernetes", "why": "Predictable performance under sustained load, fine-grained resource control, and portability across clouds — worth the operational overhead once you're running many services at real scale or have strict latency SLAs serverless cold-starts would violate.", "when": "Fall back to serverless for individual bursty/event-driven workloads even inside a Kubernetes-centric org (e.g. scheduled jobs, webhooks) — it's not all-or-nothing per service.", "conf": "high"})

    # 5. Single API gateway vs. multiple gateways
    if s["enterprise"] and s["largeTeam"]:
        t.append({"d": "Single API gateway vs. multiple gateways", "rec": "Multiple gateways, aligned to team/domain boundaries", "why": "Once different teams own different sets of microservices, a single shared gateway becomes a deployment bottleneck and a point of contention — every team's routing/policy change queues behind everyone else's. Domain-aligned gateways (or gateway instances per bounded context) let each team deploy independently, at the cost of needing a central API-management layer on top for consistent auth/observability/discovery across them.", "when": "Consolidate back toward fewer gateways if the coordination overhead of running many independent instances starts costing more than the deployment bottleneck it solved — this shows up as duplicated cross-cutting policy work (auth, rate limiting) drifting out of sync across gateways.", "conf": "medium"})
    elif s["mobile"] and s["web"]:
        t.append({"d": "Single API gateway vs. multiple gateways", "rec": "Backend-for-Frontend (BFF) — a gateway per client type (mobile, web)", "why": "Mobile and web clients typically need different data shapes, payload sizes, and auth flows — forcing both through one general-purpose gateway usually means accumulating conditional logic that serves neither client well. A thin BFF per client type lets each be optimized for its own frontend without that logic bleeding into a shared gateway.", "when": "Skip BFF and stay on a single gateway if your mobile and web clients actually consume near-identical API shapes today — add the split only once real payload/auth divergence between them shows up, not preemptively.", "conf": "medium"})
    elif s["highScale"] and s["globalMultiRegion"]:
        t.append({"d": "Single API gateway vs. multiple gateways", "rec": "Regional gateway instances behind global routing (same product, deployed per-region)", "why": "At global scale, the driver for multiple gateway instances is latency and regional failure isolation, not team ownership — a single centralized gateway (even a scalable one) forces every request through one region's network path. This is a deployment-topology decision, not a \"different product per region\" one.", "when": "Stay on a single regional deployment if your actual user base is concentrated in one geography despite \"global\" ambitions — don't pay the multi-region operational cost before the latency problem is real and measured.", "conf": "medium"})
    else:
        t.append({"d": "Single API gateway vs. multiple gateways", "rec": "Single gateway", "why": "For a small-to-mid team with one or a few client types and no strong domain-ownership boundaries yet, one gateway is simply less to build, secure, and monitor — one place to apply auth, rate limiting, and logging consistently. This is the default nearly every source on this pattern converges on: start with one, split only when a specific pain (deployment contention, client-shape divergence, or regional latency) actually shows up.", "when": "Split into multiple gateways (BFF, domain-aligned, or regional — see the three variants above) once you can name the specific pain driving it: distinct teams blocking on each other's gateway deploys, mobile/web payload needs diverging enough to matter, or measured latency from serving a global user base out of one region.", "conf": "medium"})

    # 6. Delivery methodology — Waterfall vs. Agile
    if s["fixedScope"] and not s["onPrem"]:
        t.append({"d": "Delivery methodology — Waterfall vs. Agile", "rec": "Waterfall (or a gated-Waterfall shell)", "why": "Fixed-price/fixed-scope contractual delivery or a formal RFP/statement-of-work process usually mandates sign-off gates and locked scope before work starts — that's a real external constraint, not a team preference, and Agile's assumption of evolving scope doesn't fit a contract that's already fixed it.", "when": "Move toward Agile-inside-the-gates (deliver iteratively between contractual milestones, not literally waterfall-sequential engineering) the moment the contract structure allows it — pure sequential Waterfall engineering is rarely required even when contractual gating is.", "conf": "medium"})
    elif s["enterprise"] and s["largeTeam"]:
        t.append({"d": "Delivery methodology — Waterfall vs. Agile", "rec": "Hybrid — Agile delivery inside a lightweight Waterfall-gated governance shell", "why": "Large orgs often need budget/audit gates at a portfolio level without forcing sequential engineering underneath them — this gets you both: gated checkpoints for governance, iterative sprints for the actual engineering work.", "when": "Drop the gating shell entirely and go fully Agile if your organization's actual governance need turns out lighter than assumed (e.g. no external audit/budget-cycle requirement forcing the gates).", "conf": "medium"})
    else:
        t.append({"d": "Delivery methodology — Waterfall vs. Agile", "rec": "Agile", "why": "Requirements for a net-new product build are inherently uncertain and will change as you learn — Agile's iterative cycle absorbs that change cheaply. A small team specifically is a stronger argument for Agile, not Waterfall: you can't afford the heavyweight upfront specification process Waterfall assumes, and there's usually no external contractual/regulatory gate forcing rigidity.", "when": "Move toward Waterfall-style gating only if a specific external constraint appears — a fixed-price contract, a regulatory sign-off process, or a hardware-coupled build where late-stage software change is expensive to absorb. Team size alone is not that trigger.", "conf": "high" if (s["startupMvp"] or s["smallTeam"]) else "medium"})

    # 7. Enterprise framework — TOGAF vs. SAFe
    if s["togafMentioned"] or s["safeMentioned"]:
        both = s["togafMentioned"] and s["safeMentioned"]
        mentioned_what = "both" if both else ("TOGAF" if s["togafMentioned"] else "SAFe")
        rec = "Both — TOGAF for architecture governance, SAFe for delivery coordination" if both else ("TOGAF (architecture governance)" if s["togafMentioned"] else "SAFe (scaled delivery coordination)")
        t.append({"d": "Enterprise framework — TOGAF vs. SAFe", "rec": rec, "why": "You explicitly mentioned " + mentioned_what + " — worth naming precisely what each solves so they don't get used interchangeably: TOGAF is an architecture-governance framework (a shared vocabulary and review process for multi-system/multi-domain architecture decisions), SAFe is a framework for coordinating Agile delivery across many teams at once. An org can genuinely need both, one, or neither depending on whether the pain point is architecture governance, delivery coordination, or neither yet.", "when": "Drop whichever one doesn't match your actual pain point — adopting a framework because it was mentioned rather than because it solves a real coordination problem just adds process overhead.", "conf": "high"})
    elif s["enterprise"] and s["largeTeam"]:
        t.append({"d": "Enterprise framework — TOGAF vs. SAFe", "rec": "Both worth evaluating — TOGAF for architecture governance, SAFe for delivery coordination", "why": "Large org, multiple teams, is the profile where both frameworks earn their coordination overhead: TOGAF gives a shared architecture vocabulary and review process across systems/domains, SAFe coordinates Agile delivery across many squads at once. They solve different problems (architecture governance vs. delivery coordination) and aren't a single either/or choice.", "when": "Adopt only the one matching your actual pain point (architecture governance vs. delivery coordination) rather than both by default — introducing either without a concrete coordination problem to solve just adds process weight a smaller/simpler org structure doesn't need.", "conf": "medium"})
    else:
        t.append({"d": "Enterprise framework — TOGAF vs. SAFe", "rec": "Neither — lightweight architecture decision records (ADRs) instead", "why": "Both frameworks add real coordination overhead that isn't justified below a certain org size/team count — for a small-to-mid team, a lightweight ADR per major architecture decision (context, decision, consequences) captures the same \"why did we decide this\" value TOGAF formalizes, without the process weight.", "when": "Revisit if you cross into genuinely large-org territory: multiple teams needing a shared architecture vocabulary (→ TOGAF), or coordinating Agile delivery across many squads at once (→ SAFe).", "conf": "medium"})

    # 8. IT governance — COBIT vs. ITIL
    if s["cobitMentioned"] or s["itilMentioned"]:
        both_gov = s["cobitMentioned"] and s["itilMentioned"]
        mentioned_gov = "both" if both_gov else ("COBIT" if s["cobitMentioned"] else "ITIL")
        rec = "Both — COBIT for IT risk/controls/audit governance, ITIL for day-to-day service management process" if both_gov else ("COBIT (IT risk/controls/audit governance)" if s["cobitMentioned"] else "ITIL v4 (service management process)")
        t.append({"d": "IT governance/service management — COBIT vs. ITIL", "rec": rec, "why": "You explicitly mentioned " + mentioned_gov + " — precise scoping matters here since these solve different problems from each other and from TOGAF/SAFe above: COBIT is a governance/control framework auditors and boards use to assess whether IT risk is being managed (access controls, change management oversight, audit evidence), while ITIL is an operational framework for running IT services day to day (incident response, change management process, problem management, service catalog). A regulated enterprise can need COBIT for governance, ITIL for operations, and TOGAF for architecture simultaneously — they're not competing frameworks, they answer different questions.", "when": "Drop whichever one doesn't match a real, current need — implementing COBIT's full control framework or ITIL's full process suite before you have the audit/operational-scale pressure that justifies it just adds ceremony.", "conf": "high"})
    elif s["enterprise"] and s["compliance"]:
        t.append({"d": "IT governance/service management — COBIT vs. ITIL", "rec": "Worth evaluating COBIT for IT controls/audit governance; ITIL v4 once production incident/change volume justifies formal process", "why": "Enterprise scale plus a compliance/regulated context is the profile where an auditor or board is likely to ask \"how do you govern IT risk\" — COBIT is the standard answer to that specific question. ITIL is a separate, operational concern (formal incident/change/problem management process) that's worth adopting once you have enough production services and enough on-call/change volume that ad hoc incident handling stops working, which often lags the governance need.", "when": "Skip both if your actual regulatory scope doesn't require formal IT-controls attestation and your operational scale is still small enough that lightweight on-call/change practices work fine — introducing either framework early just adds process your team will resent and route around.", "conf": "medium"})
    else:
        t.append({"d": "IT governance/service management — COBIT vs. ITIL", "rec": "Neither — lightweight incident/change practices instead", "why": "Both frameworks are built for organizations with enough scale and external audit/reporting pressure to need formalized IT governance and service-management process — below that, a simple on-call rotation, a changelog, and a basic incident postmortem template capture most of the practical value without the framework overhead.", "when": "Revisit if you take on regulated-industry customers requiring formal IT-controls evidence (→ COBIT) or your production incident/change volume outgrows informal handling (→ ITIL).", "conf": "low"})

    # 9. Edge auth (JWT) vs. service-to-service identity (mTLS + SPIFFE/SPIRE)
    if s["mtlsMentioned"] or ((s["enterprise"] or s["largeTeam"]) and (s["compliance"] or s["security"])):
        t.append({"d": "Edge auth (JWT) vs. service-to-service identity (mTLS + SPIFFE/SPIRE)", "rec": "Both, as distinct layers — JWT at the edge for who's calling in; mTLS + SPIFFE/SPIRE-issued workload identity for service-to-service calls inside the mesh", "why": "These authenticate two different things and neither substitutes for the other: JWT validation at the API Gateway/Cloud Run edge establishes who the external caller (user or client) is; it says nothing about whether \"order-service\" calling \"payment-service\" inside your cluster is actually order-service and not something that compromised the network. A common as-built gap is TLS termination + JWT at the edge only, with internal service-to-service traffic left unauthenticated/unencrypted by default — that's a real internal trust boundary most teams don't realize is open. SPIFFE/SPIRE issues short-lived, cryptographically verifiable workload identities (SVIDs) that Istio/your mesh can enforce mTLS against, giving you the \"who is actually calling whom, inside the network\" guarantee JWT-at-the-edge doesn't provide.", "when": "Skip the SPIFFE/SPIRE layer specifically (plain mesh-managed mTLS is enough) if you don't have a compliance/audit requirement for portable, independently-verifiable workload identity and you fully trust your mesh vendor's internal certificate management — SPIRE is a genuine operational add, not a default for every mesh deployment.", "conf": "high"})
    elif s["enterprise"] or s["largeTeam"]:
        t.append({"d": "Edge auth (JWT) vs. service-to-service identity (mTLS)", "rec": "JWT at the edge now; add mesh-enforced mTLS between services once service count/team count justify a mesh at all", "why": "At moderate scale, edge JWT auth plus your cloud provider's VPC-level network isolation is a reasonable trust boundary — full service-to-service mTLS is usually adopted alongside the service mesh decision (see Service Mesh above) rather than as a separate earlier investment.", "when": "Don't wait past the point where you adopt a service mesh at all — once Istio (or similar) is in place for traffic management/observability reasons, turning on mesh-enforced mTLS between services is close to free, so there's little reason to leave internal traffic unauthenticated once the mesh exists.", "conf": "medium"})

    # 10. Media server topology for video/voice conferencing
    if s["videoConferencing"]:
        t.append({"d": "Media server topology — P2P mesh vs. SFU vs. MCU", "rec": "SFU (Selective Forwarding Unit) — e.g. LiveKit, mediasoup, or Jitsi Videobridge if self-hosting; Daily.co/Agora/100ms if you'd rather buy than build", "why": "P2P mesh (every client sends a stream to every other client) only holds up to roughly 3-5 participants before upload bandwidth and CPU explode combinatorially — it's the wrong default for anything billed as \"group calls.\" An SFU forwards streams without re-encoding them, which is the standard middle ground from 5 to hundreds/thousands of participants. MCU (server decodes, mixes, and re-encodes one composite stream) trades server CPU cost for lower client bandwidth/CPU — useful for low-power endpoints or SIP/telephony bridging, rarely the primary topology in 2026. Whichever you pick, you also need TURN relay servers (coturn is the standard self-hosted option) for the meaningful share of real users behind symmetric NAT/restrictive firewalls who can't connect via STUN/direct P2P alone — this isn't optional hardening, calls silently fail without it for those users.", "when": "Stay on P2P mesh only for a genuine 1:1 or small (≤4 person) fixed-size call feature where you want zero media-server cost. Move to MCU (or a hybrid SFU+MCU) if most participants are low-power/bandwidth-constrained endpoints, or you need to bridge into legacy SIP/telephony. Buy (Daily.co/Agora/100ms/LiveKit Cloud) instead of self-hosting the SFU if you don't have the ops capacity for media-plane infrastructure — this is a deep enough specialty that \"build it ourselves\" is a real cost most teams underestimate.", "conf": "high"})

    # 11. Micro-frontends vs. a single frontend app
    if s["microFrontend"] or (s["enterprise"] and s["largeTeam"] and s["mobile"] and s["web"]):
        rec = "Micro-frontends via Webpack/Rspack Module Federation, or single-spa if you need to mix frameworks across teams" if s["microFrontend"] else "Worth evaluating Module Federation once distinct teams own distinct customer-facing apps (as yours do)"
        t.append({"d": "Micro-frontends (Module Federation) vs. a single frontend app", "rec": rec, "why": "Micro-frontends earn their coordination overhead specifically when separate teams need to deploy separate parts of the UI on independent schedules without blocking on each other — Module Federation (Webpack/Rspack) is the dominant 2026 mechanism, letting apps expose/consume modules at runtime with shared-dependency negotiation so you're not shipping N copies of React. single-spa is the framework-agnostic alternative when different teams are on genuinely different frameworks. A shared design-system package (versioned npm package or a federated \"shared\" remote) is what keeps the UI consistent across independently-deployed apps — without it, micro-frontends drift visually team by team.", "when": "Don't adopt this for a single team or a product without real team-ownership boundaries yet — the operational cost (multiple CI/CD pipelines, shared-dependency version negotiation, cross-team API contracts) reliably exceeds the benefit below roughly 15-20 engineers or a single product roadmap. A modular monolith frontend (or an Nx/Turborepo monorepo without runtime federation) gets most of the codebase-modularity benefit at a fraction of the operational complexity — reach for that first, and only add runtime federation once independent deploy cadence is the actual blocker.", "conf": "high" if s["microFrontend"] else "medium"})

    # 12. Saga pattern — choreography vs. orchestration
    if s["sagaWorkflow"]:
        orchestration_fit = s["enterprise"] or s["largeTeam"] or s["finance"]
        rec = "Orchestration — a durable workflow engine (Temporal.io, or AWS Step Functions if you're AWS-native) drives the saga as an explicit state machine" if orchestration_fit else "Choreography for now (services react to each other's events) — but keep the step count small"
        t.append({"d": "Saga pattern — Choreography vs. Orchestration", "rec": rec, "why": "Splitting a checkout/order flow (reserve inventory → charge payment → book shipping) across services means no single database transaction spans all three — you need eventual consistency with explicit compensating actions if a later step fails. Choreography (each service publishes an event, the next reacts) has no central coordinator and stays simple for 2-4 steps, but the flow logic gets smeared across services and becomes hard to trace or debug once it grows — that's exactly the failure mode a durable orchestration engine (Temporal, Step Functions) solves: an explicit, observable state machine that tracks \"where is this order stuck\" and handles retries/compensation for you. Either way, publish saga events via the transactional outbox pattern (write the event to an outbox table in the same local transaction as the business update, then use CDC — e.g. Debezium — to publish reliably) — writing to your DB and separately publishing to a broker as two operations is the classic dual-write bug that silently loses events on a crash between the two.", "when": "Move from choreography to orchestration the moment the saga grows past roughly 4-5 steps, needs multiple distinct compensation paths, or \"why is this order stuck\" becomes a support/debugging problem nobody can answer quickly. Never reach for two-phase-commit (XA transactions) across services as an alternative — it requires synchronous cross-service locking that kills availability during any partial failure and isn't supported by most modern brokers; the field has converged on saga+compensation, not 2PC, for this problem.", "conf": "high"})

    # 13. Multi-tenant isolation — silo vs. pool vs. bridge
    if s["multiTenant"]:
        t.append({"d": "Multi-tenant isolation — Silo vs. Pool vs. Bridge", "rec": "Bridge — shared compute, tenant-isolated data via Postgres Row-Level Security (RLS) with a tenant_id on every table", "why": "Silo (dedicated infrastructure per tenant) gives the strongest isolation and simplest compliance story but doesn't scale economically past a small number of tenants — you're running N copies of your entire stack. Pool (fully shared schema, no enforced boundary beyond app code) is cheapest but relies entirely on every query remembering a WHERE tenant_id = ? clause — one missed clause, one raw-SQL escape hatch, or one buggy ORM query leaks another tenant's data, and this is the single most common cause of real cross-tenant breaches. The bridge model — shared compute/schema with Postgres RLS enforcing tenant_id at the database layer, not just in application code — is the dominant 2026 pattern for SaaS serving many small-to-mid tenants: it scales cheaply and still gives DB-enforced (not just app-trusted) isolation. Cache keys and rate limits also need tenant_id namespacing (per-tenant Redis key prefixes, per-tenant token buckets) or one tenant's load starves everyone else's — the \"noisy neighbor\" problem.", "when": "Move specific tenants to silo (dedicated DB/infra) when they're large enough, regulated enough (healthcare/finance/government), or contractually demanding enough to require guaranteed data residency or isolation guarantees RLS can't promise on paper — this is often a targeted exception applied to a handful of accounts, not an all-or-nothing switch. Schema-per-tenant is a legitimate middle ground for hundreds (not thousands) of mid-size tenants needing more customization/backup granularity than shared-schema-RLS offers, but it becomes a migration/connection-pooling problem well before thousands of tenants.", "conf": "high"})

    # 14. Marketplace payments — build vs. Stripe Connect
    if s["marketplace"]:
        t.append({"d": "Marketplace payments — build your own ledger/escrow vs. Stripe Connect", "rec": "Stripe Connect (or Adyen for Platforms / Mangopay if geography or true held-funds escrow needs push you off Stripe)", "why": "Rolling your own split-payment/escrow ledger means becoming (or partnering with) a licensed money transmitter, and building KYC/AML checks, 1099-K tax reporting, PCI compliance, and chargeback/dispute handling from scratch — this is consistently cited as one of the most expensive, riskiest mistakes marketplace founders make, and it's rarely a differentiator worth owning. Stripe Connect is purpose-built for this: it handles seller onboarding/KYC, split payments via application_fee_amount, delayed payouts (functional escrow via payout timing), 1099-K generation, and fraud screening (Radar) as a package. Adyen for Platforms and Mangopay are the credible alternatives when you need true held-funds escrow wallets (not just delayed transfer) or specific EU/multi-currency handling Stripe doesn't fit as well.", "when": "Consider Custom Stripe Connect accounts (more control, more compliance burden pushed back to you) only once volume/brand requirements justify owning more of the onboarding UX. Consider a non-Stripe provider specifically when your geography, currency mix, or a genuine escrow-wallet (not delayed-transfer) requirement is a hard constraint Stripe can't satisfy — verify this against your actual regulatory footprint before switching, not preemptively.", "conf": "high"})

    # 15. ML feature infrastructure — full feature store vs. shared code repo
    if s["mlFeatureStore"]:
        feature_store_justified = s["enterprise"] or s["highScale"]
        rec = "A managed or open-source feature store (Feast if you want no lock-in, Tecton/SageMaker/Databricks Feature Store if you're already on that platform)" if feature_store_justified else "A shared, versioned feature-computation code repo (no dedicated feature store yet)"
        t.append({"d": "ML feature infrastructure — full feature store vs. a shared feature-code repo", "rec": rec, "why": "The core risk here is training/serving skew: feature logic written once for offline batch training (Spark/SQL) and separately for low-latency online inference silently drifts apart and degrades production accuracy without anyone noticing until it shows up in model performance. A full feature store (Feast, Tecton, SageMaker/Databricks Feature Store) pays off once multiple models/teams share features, you need sub-second-fresh online serving (Redis/DynamoDB-backed), and you're fighting real skew across pipelines — but it's a dual-database system (offline store + online store + a sync job) that's genuine operational overhead most teams don't need on day one. Whatever you choose, put a model registry (MLflow is the open-source default; Weights & Biases if you want richer collaborative dashboards) in front of production models from the start — tracking \"what model is actually live\" via file paths or Slack messages instead of a registry is what makes safe rollback impossible later.", "when": "Move to a full feature store once you have more than one model consuming the same features, or a product need for sub-second feature freshness (e.g. real-time fraud scoring) that a nightly/hourly batch job can't satisfy. Stay on a shared code repo (with the same transformation logic imported by both the training job and the serving path, not reimplemented) if you have one or two models and daily/hourly freshness is genuinely enough — this is the more common case than the feature-store marketing suggests.", "conf": "medium"})

    # 16. Search index technology
    if s["searchRecommendation"]:
        rec = "Typesense or Meilisearch — near-zero-ops, fast, good enough for small-to-mid catalogs" if (not s["dataHeavy"] and not s["enterprise"] and not s["highScale"]) else "Elasticsearch/OpenSearch for deep relevance/analytics control, or Algolia if you'd rather pay for a fully-managed, typo-tolerant experience and skip the ops"
        t.append({"d": "Search index — Postgres full-text vs. Elasticsearch/OpenSearch vs. Algolia/Typesense", "rec": rec, "why": "Using Postgres LIKE/ILIKE (or an untuned tsvector) as \"search\" is the most common early mistake here — no typo tolerance, poor relevance ranking, and full-table-scan-shaped performance that degrades badly past tens of thousands of rows; Postgres full-text search (tsvector + GIN index) is a legitimate low-cost option only for small catalogs with modest requirements. Elasticsearch/OpenSearch gives the deepest relevance tuning and analytics/aggregation power at the cost of real operational investment (cluster sizing, reindexing pipelines); OpenSearch specifically avoids Elastic's SSPL/Elastic License 2.0 restrictions. Algolia and Typesense/Meilisearch trade some control for either a fully managed experience (Algolia — fast, typo-tolerant, merchandising features, higher per-record cost) or a near-zero-ops single-binary engine (Typesense/Meilisearch — predictable low latency, practical ceiling around tens of GB per node). For recommendations specifically: start with collaborative filtering + a content-based/popularity fallback (the fallback matters — pure collaborative filtering fails hard on new users/items with no interaction history, the \"cold start\" problem) before investing in a learned two-tower/ranking model, which is expensive to build and only worth it once basic relevance is solid and you have enough interaction data to train on.", "when": "Move off Postgres full-text the moment typo-tolerance, faceted filtering, or catalog size (tens of thousands of rows and growing) become real product problems. Move from Algolia/Typesense to Elasticsearch/OpenSearch (or add it alongside) once you need deep custom relevance tuning or heavy internal analytics/aggregations on the same data most managed search products don't expose. If combining keyword and semantic/vector search, fuse results with Reciprocal Rank Fusion (rank-based fusion) rather than trying to normalize incompatible BM25/cosine-similarity score scales directly.", "conf": "medium"})

    # 17. Semantic-routing / AI-guardrail service
    if s["routingGuardrailService"] or (s["agentic"] and (s["compliance"] or s["security"])):
        t.append({"d": "Semantic-routing / guardrail logic — dedicated service vs. embedded per-agent", "rec": "A dedicated routing/guardrail service (an AI gateway) — e.g. Portkey or Cloudflare AI Gateway if you want routing+guardrails+observability bundled, or Not Diamond/OpenRouter's Auto Router/RouteLLM (open source) if you specifically want routing without a full gateway product", "why": "Two problems compound once you have more than one model or more than one agent/service making LLM calls: (1) cost/latency waste from sending every request to a frontier model when most queries are simple enough for a cheap one — RouteLLM's own benchmark gets ~95% of GPT-4-level quality while routing only ~14% of queries to the strong model, which is the order of magnitude at stake; (2) guardrail duplication — PII redaction, prompt-injection/jailbreak detection, and content-policy checks re-implemented (or forgotten) per agent instead of enforced once, centrally, with one audit trail. Centralizing both in a dedicated service — commonly the same service, since both need to intercept every request/response — fixes both at once. Guardrail checks should split by cost: fast pre-call checks (regex/PII pattern match, a small jailbreak classifier) stay synchronous in the request path since they can also short-circuit an unsafe request before it reaches an expensive model; slower post-call checks (LLM-as-judge groundedness, deep content classifiers) are usually sampled/async rather than blocking every response.", "when": "Skip a dedicated routing/guardrail service if you're only calling one model from one place — a single hardcoded model choice with inline validation is simpler and correct until that changes; adding this layer before you actually have 2+ models with different cost/quality profiles in play is premature complexity. Start with rule-based routing (keyword/length conditions) before reaching for an embedding-similarity or trained-classifier router — a k-NN or rules baseline is often competitive and much cheaper to build/maintain than a fully learned router.", "conf": "high" if s["routingGuardrailService"] else "medium"})

    return t


# ---------- Cost, throughput, and governance ----------


def pick_cost_optimization(s):
    items = []
    if s["startupMvp"]:
        items.append({"t": "Serverless / pay-per-use compute with scale-to-zero", "w": "Avoids paying for idle capacity — the single biggest cost lever for a small team with unpredictable early-stage traffic."})
    else:
        items.append({"t": "Continuous right-sizing: review utilization weekly, tune autoscaling floor/ceiling", "w": "Most infra waste comes from static sizing decisions made at launch and never revisited."})
    if s["highScale"] or s["enterprise"]:
        items.append({"t": "Reserved/Savings Plans or Committed Use Discounts for steady-state baseline load; spot/preemptible instances for batch & non-prod", "w": "Typically cuts 30–60% off compute spend for predictable baseline load without sacrificing burst headroom."})
    items.append({"t": "Tiered storage lifecycle policies (hot → warm → cold/archive)", "w": "Most data cools quickly; automatic tiering avoids paying hot-storage rates for rarely-accessed data."})
    items.append({"t": "Route LLM calls by task complexity — small open-weight models (4B–12B) for high-volume/simple tasks, frontier models reserved for complex reasoning", "w": "LLM inference is billed per token; routing cheap tasks to cheap models is the highest-leverage AI cost control available."})
    items.append({"t": "Cache LLM responses and embeddings for repeated or near-duplicate queries", "w": "Avoids re-paying inference cost for requests you've effectively already answered."})
    if s["ragNeed"]:
        items.append({"t": "Batch embedding generation instead of real-time per-document embedding", "w": "Batching cuts API overhead and often qualifies for lower batch-inference pricing."})
    items.append({"t": "FinOps tagging with per-team/per-service showback or chargeback dashboards", "w": "Visibility is the prerequisite for optimization — teams cut their own waste once they can see it."})
    return items


# ---------- Directional monthly cost estimate (FinOps lens) ----------
# Deliberately a RANGE, not a point estimate — see KICKOFF_BRIEF.md's known-traps note and
# ../docs/use-case-knowledge-base/09-cost-estimation-methodology.md for full sourcing.


def pick_cost_estimate(s, ctx=None):
    scale = "high" if (s["enterprise"] and s["highScale"]) else "medium" if (s["highScale"] or s["enterprise"] or s["realtime"]) else "low"

    if s["onPrem"]:
        compute_band = {"label": "Not applicable — capex, not opex", "detail": "Self-managed hardware is a one-time/amortized hardware+facilities cost, not a monthly cloud bill — budget separately (servers, colo/rack space, networking gear, and the ops headcount to run it)."}
    elif scale == "high":
        compute_band = {"label": "$10,000–$50,000+/mo", "detail": "Enterprise Kubernetes footprint (100+ nodes) — highly dependent on node count and instance class; this is an order-of-magnitude planning band, not a quote."}
    elif scale == "medium":
        compute_band = {"label": "$300–$1,500/mo", "detail": "Serverless containers or a small-to-mid Kubernetes cluster (3–6 nodes) — control plane + node cost + load balancer + storage."}
    else:
        compute_band = {"label": "$0–$500/mo", "detail": "Serverless/FaaS at low-to-moderate traffic — much of this typically lands inside cloud free tiers (e.g. Cloud Run's 2M free requests/mo, Lambda's 1M free requests/mo); budget for min-instances/cold-start mitigation pushing toward the top of this range."}

    if scale == "high":
        db_band = {"label": "$1,000–$5,000+/mo", "detail": "HA multi-AZ managed Postgres, a clustered/replicated Redis, and (if applicable) a production-tier vector database at real scale."}
    elif scale == "medium":
        db_band = {"label": "$150–$900/mo", "detail": "Mid-tier managed Postgres, a small managed Redis, and a vector DB starter-to-production tier if you have a RAG/knowledge-base requirement."}
    else:
        db_band = {"label": "$25–$100/mo", "detail": "A small managed Postgres instance plus a small managed Redis instance — the realistic floor for \"managed, not self-run\" databases."}
    vector_db_note = ""
    if s["knowledgeBase"] or s["agentic"]:
        vector_db_note = " Vector DB specifically: free/starter tier ($0–$25/mo) is realistic pre-launch; budget $50–$700/mo once you have real document/query volume, climbing further at very large index sizes (Pinecone/Qdrant Cloud production tiers)."

    uses_llm = s["chatbot"] or s["agentic"] or s["knowledgeBase"] or s["voice"]
    llm_band = None
    if uses_llm:
        hosting = (ctx or {}).get("hosting") or {}
        is_local = bool(re.match(r"^local", (hosting.get("rec") or "").strip(), re.IGNORECASE))
        if is_local:
            llm_band = {"label": "$0 direct API spend", "detail": "Self-hosted/local inference (Ollama or similar) means no per-token API bill — the real cost shows up as GPU compute in the line above, not here. This is the actual cost trade-off local hosting makes: capex/fixed infra cost instead of variable per-token spend.", "table": None}
        else:
            volume_label = "~30,000 conversations/day" if scale == "high" else "~3,000 conversations/day" if scale == "medium" else "~1,000 conversations/day"
            mult = 30 if scale == "high" else 3 if scale == "medium" else 1
            rows = [
                {"tier": "Budget open-weight (via OpenRouter — Llama/Qwen/Mistral-class)", "low": 3 * mult, "high": 50 * mult},
                {"tier": "Mid-tier hosted (Gemini Flash-class)", "low": 115 * mult, "high": 160 * mult},
                {"tier": "Frontier (Claude Sonnet-class / GPT flagship-class)", "low": 1050 * mult, "high": 1350 * mult},
            ]
            llm_band = {
                "label": f"${rows[0]['low']:,}–${rows[2]['high']:,}/mo depending on model tier",
                "detail": f"At an illustrative volume of {volume_label} (~1,500 input + 500 output tokens/conversation) — the model-tier choice swings this by roughly two orders of magnitude, which is why \"route cheap tasks to cheap models\" (see Cost & Resource Optimization below) is the single highest-leverage lever here, not infrastructure tuning. Prompt caching can cut repeat-context cost 50–90% further for RAG/chatbot workloads with long system prompts.",
                "table": rows,
            }

    return {"scale": scale, "computeBand": compute_band, "dbBand": db_band, "vectorDbNote": vector_db_note, "llmBand": llm_band, "usesLLM": uses_llm}


def pick_concurrency(s):
    # A stated numeric target is the binding constraint for this section, so it leads and is
    # quoted verbatim. detect_signals() parsed no numbers at all before, so an explicit
    # "in under three seconds" contributed nothing and the reader got generic latency advice.
    lt = s.get("latencyTarget")
    _lead = []
    if lt:
        if lt["ms"] >= 1000:
            budget = (f"Budget it explicitly end-to-end: retrieval, model generation and any tool "
                      f"calls all have to fit inside {lt['ms'] / 1000}s together, not each.")
        else:
            budget = (f"At {lt['ms']}ms end-to-end there is no room for a synchronous LLM call in the "
                      f"request path — serve from cache/precomputed results, or return async and stream.")
        _lead.append({"t": f"Meet your stated target: {lt['text']} end-to-end",
                      "w": f'You specified "{lt["text"]}", so treat it as this section\'s acceptance '
                           f"criterion rather than a general aspiration. {budget} Measure at P95 against "
                           f"the full user-visible path, not per-component averages — component budgets "
                           f"that each look fine routinely add up past the target."})
    items = [
        {"t": "Async, non-blocking I/O throughout the request path", "w": "Blocking calls (especially to LLMs or external APIs) are the most common throughput killer — async lets one instance serve many concurrent requests."},
        {"t": "Connection pooling for database and external API clients", "w": "Avoids connection-setup overhead becoming the bottleneck under concurrent load."},
    ]
    if s["realtime"] or s["highScale"]:
        items.append({"t": "Horizontal autoscaling tuned on custom metrics (queue depth, P95 latency) rather than CPU alone", "w": "CPU-based autoscaling reacts too late for bursty or latency-sensitive AI workloads."})
    if s["highScale"]:
        items.append({"t": "Read replicas, and sharding once a single primary can't serve combined read+write load", "w": "Splitting read traffic to replicas is usually the cheapest scaling step before resharding is needed."})
    items.append({"t": "CDN / edge caching for static and semi-static responses", "w": "Removes repeat load from origin servers entirely for cacheable content."})
    items.append({"t": "Queue-based load leveling with bounded queues and backpressure", "w": "Protects downstream services from being overwhelmed during traffic spikes; unbounded queues just delay the failure."})
    if s["chatbot"] or s["agentic"]:
        items.append({"t": "Stream LLM responses (SSE/WebSocket) instead of waiting for full completion", "w": "Improves perceived latency and lets clients start rendering before generation finishes — important under concurrent chat load."})
    if s["agentic"]:
        items.append({"t": "Circuit breakers and timeouts on every external tool call inside agent loops", "w": "One slow tool call in a multi-step agent workflow shouldn't be able to hang the whole request."})
    return _lead + items


def pick_governance(s):
    kra = [
        "System Reliability & Availability",
        "Cost Efficiency & Resource Utilization",
        "AI Output Quality & Safety",
        "Delivery Velocity & Engineering Throughput",
    ]
    kpi = [
        "P95 API latency < 200ms, P99 < 500ms" if s["realtime"] else "P95 API latency < 800ms, P99 < 2s",
        "Error rate < 0.1% of requests (5xx)",
        "Cost per request / cost per active user, tracked weekly",
        "Deployment frequency & lead time for changes (DORA metrics)",
    ]
    if s["ragNeed"] or s["chatbot"]:
        kpi.append("RAG groundedness / hallucination rate on sampled responses")
    if s["agentic"]:
        kpi.append("Agent task success rate & average tool-calls per completed task")
    sla = []
    if s["compliance"] or s["enterprise"]:
        sla.append("99.95% uptime (≈22 min downtime/month) — penalty-bearing external SLA")
    else:
        sla.append("99.5% uptime target (≈3.6 hrs downtime/month) — appropriate for pre-PMF/early-stage products")
    sla.append("Support response time: P1 < 1hr, P2 < 4hrs, P3 < 1 business day")
    rci = [
        "MTTD (mean time to detect) target < 5 min, via SLO burn-rate alerting rather than hard thresholds alone",
        f"MTTR (mean time to resolve) target: {'< 1hr for P1 incidents' if s['enterprise'] else '< 4hrs for P1 incidents'}",
        "Blameless postmortem within 48hrs of every P1/P2 incident, with tracked action items to closure",
        "Error-budget policy: freeze non-essential releases when SLO burn exceeds budget for the period",
    ]
    return {"kra": kra, "kpi": kpi, "sla": sla, "rci": rci}


def apply_domain_floors(rec: dict, s: dict) -> None:
    """Mirrors index.html's applyDomainFloors() — see that function's comment for the full
    rationale and the deliberate scope decision (only cloud/containers/database/iam/
    observability/messaging/compute/frontend/architecture are touched, not every category).

    An if/elif chain, not independent ifs: these four are meant to be mutually exclusive.
    """
    if s.get("browserExtension"):
        why = ("Browser extensions run entirely inside the browser sandbox and ship through the "
               "browser's own extension store — there is no server-side deployment to host.")
        rec["cloud"] = domain_floor_pick("no server-side hosting needed for a browser extension", why)
        rec["containers"] = domain_floor_pick("nothing runs server-side to containerize", why)
        rec["database"] = domain_floor_pick(
            "no server-side datastore — use the browser's own storage API (chrome.storage / IndexedDB) for local state", why)
        rec["iam"] = domain_floor_pick("no server-side user accounts to authenticate", why)
        rec["observability"] = domain_floor_pick(
            "no server infrastructure to observe — use a client-side error-reporting SDK instead", why)
        rec["messaging"] = domain_floor_pick("no server-side services to connect via messaging", why)
        rec["compute"] = domain_floor_pick("logic runs inside the browser sandbox, not on a provisioned compute tier", why)
        rec["architecture"] = domain_floor_pick("a single browser extension has no service architecture style to choose", why)
        rec["frontend"] = {
            "v": "Manifest V3 browser extension (background service worker + popup UI in vanilla JS or a lightweight framework)",
            "conf": "high", "why": why,
        }
    elif s.get("desktopApp"):
        why = ("A cross-platform desktop application with no backend server runs entirely on the "
               "user's own machine — there is nothing to host, scale, or authenticate against server-side.")
        rec["cloud"] = domain_floor_pick("no server-side hosting — the app runs on the user's own machine", why)
        rec["containers"] = domain_floor_pick("nothing runs server-side to containerize", why)
        rec["iam"] = domain_floor_pick(
            "no server-side user accounts — use the OS's own user session if any access control is needed", why)
        rec["observability"] = domain_floor_pick(
            "no server infrastructure to observe — use a desktop crash-reporting SDK (e.g. Sentry) instead", why)
        rec["messaging"] = domain_floor_pick("no server-side services to connect via messaging", why)
        rec["compute"] = domain_floor_pick("runs on the user's own machine, not a provisioned compute tier", why)
        rec["architecture"] = domain_floor_pick("a single desktop application has no service architecture style to choose", why)
        rec["frontend"] = {
            "v": "Cross-platform desktop UI (Tauri or Electron, matched to your team's language) with an embedded SQLite database for local persistence",
            "conf": "high", "why": why,
        }
        rec["database"] = {"v": "Embedded SQLite (bundled with the app, no server-side database)", "conf": "high", "why": why}
    elif s.get("cliTool"):
        why = ("A local command-line tool runs on the operator's own machine or a CI runner — "
               "there is no server-side surface to host, and no end-user-facing UI to build.")
        rec["cloud"] = domain_floor_pick("no server-side hosting for a local CLI tool", why)
        rec["containers"] = domain_floor_pick(
            "nothing runs server-side to containerize (package the tool itself via pip/pipx or a single binary instead)", why)
        rec["iam"] = domain_floor_pick("no server-side user accounts for a local CLI tool", why)
        rec["observability"] = domain_floor_pick("no server infrastructure to observe — plain logging to stdout or a log file is enough", why)
        rec["messaging"] = domain_floor_pick("no server-side services to connect via messaging", why)
        rec["compute"] = domain_floor_pick("runs on the operator's own machine or a CI runner, not a provisioned compute tier", why)
        rec["architecture"] = domain_floor_pick("a single CLI tool has no service architecture style to choose", why)
        rec["frontend"] = domain_floor_pick(
            "command-line interface only — no web/mobile frontend (argparse, Click, or Typer for Python; Cobra for Go; etc.)", why)
        rec["database"] = domain_floor_pick(
            "no server-side database — read/write local files directly, or add embedded SQLite only if you need structured queries over the data", why)
    elif s.get("staticSite"):
        why = ("A static site with no backend has nothing to compute or persist server-side — "
               "it only needs files served from a CDN.")
        rec["cloud"] = {
            "v": "Static hosting / CDN (Cloudflare Pages, Vercel, Netlify, or S3 + CloudFront) — not a full IaaS cloud tier",
            "conf": "high", "why": why,
        }
        rec["containers"] = domain_floor_pick("static assets are served directly from a CDN — no server process to containerize", why)
        rec["database"] = domain_floor_pick("no server-side data to persist for a static site", why)
        rec["iam"] = domain_floor_pick("no user accounts for a static site", why)
        rec["observability"] = domain_floor_pick(
            "no server infrastructure to observe — a lightweight client-side analytics snippet is enough if desired", why)
        rec["messaging"] = domain_floor_pick("no server-side services to connect via messaging", why)
        rec["compute"] = domain_floor_pick("pure static delivery — no server compute tier", why)
        rec["architecture"] = domain_floor_pick("a static site has no application architecture style — just markup and assets", why)


# ---------- Top-level entry point ----------


def apply_exclusions(rec: dict, s: dict) -> dict:
    """Mirrors index.html's applyExclusions(): overwrite picks the user explicitly ruled out.

    Applied at the one place every category is in scope rather than threading a guard through 47
    pick functions — one auditable list, and a new category cannot silently miss the check.
    """
    ex = (s or {}).get("excluded") or {}

    # Kubernetes is a DOWNGRADE, not a removal: ruling out Kubernetes is not ruling out containers.
    if ex.get("kubernetes") and not ex.get("containers"):
        rec["containers"] = {
            "v": "Docker + managed serverless containers (Cloud Run / Fargate / Container Apps) — not Kubernetes",
            "conf": "high", "excluded": True,
            "why": "You ruled out Kubernetes, so this is the container story without a control plane "
                   "to run: the same images on a managed serverless-container runtime. If you also "
                   "want to avoid containers entirely, say so and this drops to plain VM/PaaS deployment."}
    if ex.get("containers"):
        rec["containers"] = excluded_pick("containers")
    if ex.get("microservices"):
        rec["architecture"] = {
            "v": "Modular monolith (single deployable, module boundaries enforced in-code)",
            "conf": "high", "excluded": True,
            "why": "You ruled out microservices. A modular monolith keeps the bounded-context "
                   "discipline — clear module seams, no cross-module database access — without the "
                   "distributed-systems cost, and remains the migration path if you change your mind."}
    if ex.get("messaging"):
        rec["messaging"] = excluded_pick("messaging/streaming")
    if ex.get("cache"):
        rec["cache"] = excluded_pick("caching")
    if ex.get("database"):
        rec["database"] = excluded_pick("a database")
    # Found via a manual "on-premises... no public cloud" QA scenario: BOTH s.onPrem and
    # ex.cloud can fire on the same sentence at once ("on-premises" triggers the former,
    # "no public cloud" separately matches EXCLUSION_TERMS["cloud"]). Since this block runs
    # after pick_cloud, an unconditional overwrite here clobbered pick_cloud's own, more useful
    # on-prem-specific answer ("On-premises / private infrastructure...") with the generic
    # "Not recommended — you excluded cloud hosting" stub — the phrasing that gave the tool
    # MORE information produced the LESS useful answer. Skip the generic overwrite when
    # pick_cloud's on-prem branch already produced a real answer for the same intent.
    if ex.get("cloud") and not s.get("onPrem"):
        rec["cloud"] = excluded_pick("cloud hosting")
    if ex.get("frontend"):
        rec["frontend"] = excluded_pick("a web/mobile frontend")
    if ex.get("mesh"):
        rec["mesh"] = excluded_pick("a service mesh")
    if ex.get("iam"):
        rec["iam"] = excluded_pick("a managed identity provider")
    if ex.get("observability"):
        rec["observability"] = excluded_pick("an observability vendor")
    if ex.get("languages"):
        rec["languages"] = _pick_language_alternative(s, s.get("excludedLanguageTerms") or set())

    # rag/llm carry different shapes from the {v, why, conf} cards.
    if ex.get("rag"):
        rec["rag"] = {"name": "Not recommended — you excluded RAG", "conf": "high", "excluded": True,
                      "why": "You ruled out retrieval-augmented generation, so no retrieval pattern is recommended."}
        rec["vector_db_placement"] = dict(rec.get("vector_db_placement") or {}, needed=False, excluded=True,
                                          dbChoice="Not required — RAG excluded",
                                          why="No vector database is needed because retrieval itself was ruled out.")
    if ex.get("llm"):
        rec["llm"] = [{"name": "Not recommended — you excluded LLMs", "tag": "excluded by requirement"}]

    # Vendor comparisons are computed from the PRE-exclusion picks, so without this an excluded
    # category still ships a live vendor recommendation — cloud="you excluded cloud hosting"
    # alongside cloud_vendor={"v": "AWS"}. Mark them suppressed rather than deleting the key, so
    # an MCP client sees WHY the comparison is absent instead of a missing field.
    def _suppress(key):
        if rec.get(key):
            rec[key] = dict(rec[key], suppressed=True,
                            why="Suppressed — this category was excluded by the requirement, so a "
                                "vendor comparison for it would contradict the recommendation.")

    if ex.get("cloud"):
        _suppress("cloud_vendor")
    if ex.get("containers") or ex.get("kubernetes"):
        _suppress("orchestrator_vendor")
    if ex.get("database"):
        _suppress("database_vendor")
    if ex.get("messaging"):
        _suppress("messaging_vendor")
    if ex.get("observability"):
        _suppress("observability_vendor")
    if ex.get("frontend"):
        _suppress("frontend_vendor")
    if ex.get("llm"):
        _suppress("llm_provider_vendor")
    if ex.get("rag") or ex.get("llm"):
        _suppress("vector_db_vendor")
    if ex.get("serverless"):
        _suppress("compute_platform_vendor")
    if ex.get("api"):
        _suppress("gateway_vendor")
    return rec


def recommend_stack(requirement_text: str) -> dict:
    """Mirrors index.html's analyze() function: runs the full rule engine over a free-text
    requirement and returns {signals, recommendations}. Category keys are snake_case (this is
    server-side Python, not a mechanical port of index.html's rendering code) — only signal
    dict keys and vendor-table keys stay camelCase, per this module's docstring."""
    if not requirement_text or not requirement_text.strip():
        raise ValueError("requirement_text must be non-empty")

    s = detect_signals(requirement_text)

    cloud = pick_cloud(s)
    compute = pick_compute(s)
    msg = pick_messaging(s)
    db = pick_database(s)
    containers = pick_containers(s)
    obs = pick_observability(s)
    fe = pick_frontend(s)
    llm = pick_llm(s)
    rag = pick_rag(s)
    gw = pick_gateway(s)
    cicd = pick_cicd(s)
    hosting = pick_hosting_location(s)

    recommendations = {
        "cloud": cloud,
        "gateway": gw,
        "iam": pick_iam(s),
        "languages": pick_languages(s),
        "architecture": pick_architecture(s),
        "compute": compute,
        "messaging": msg,
        "mesh": pick_mesh(s),
        "cache": pick_cache(s),
        "database": db,
        "containers": containers,
        "observability": obs,
        "frontend": fe,
        "cicd": cicd,
        "dns": pick_dns(s),
        "hybrid_connectivity": pick_hybrid_connectivity(s, cloud),
        "audit_logging": pick_audit_logging(s),
        "privileged_access": pick_privileged_access(s),
        "testing_strategy": pick_testing_strategy(s),
        "network_boundary": pick_network_boundary(s),
        "multi_cloud_bridging": pick_multi_cloud_bridging(s),
        "security_gates": pick_security_gates(s),
        "docs": pick_docs(s),
        "llm": llm,
        "mcp_servers": pick_mcp(s),
        "rag": rag,
        "guardrails": pick_guardrails(s),
        "integration_guidance": pick_integration_guidance(s),
        "cost_optimization": pick_cost_optimization(s),
        "cost_estimate": pick_cost_estimate(s, {"hosting": hosting}),
        "concurrency": pick_concurrency(s),
        "governance": pick_governance(s),
        "tradeoffs": pick_tradeoffs(s),
        "model_orchestration": pick_model_orchestration(s),
        "hosting_location": hosting,
        "compute_tier": pick_compute_tier(s),
        "runtime": pick_runtime(s),
        "interface_topology": pick_interface_topology(s),
        "mcp_vs_api": pick_mcp_vs_api(s),
        "guardrail_pipeline": pick_guardrail_pipeline(s),
        "vector_db_placement": pick_vector_db_placement(s, rag),
        # Vendor/alternatives comparisons (Groups 1-4) — see module docstring.
        "cloud_vendor": pick_cloud_vendor(cloud),
        "compute_platform_vendor": pick_compute_platform(s, compute),
        "orchestrator_vendor": pick_orchestrator(s, containers),
        "gateway_vendor": pick_gateway_vendor(s),
        "database_vendor": pick_database_vendor(db),
        "messaging_vendor": pick_messaging_vendor(s, msg),
        "llm_provider_vendor": pick_llm_provider(s, llm),
        "vector_db_vendor": pick_vector_db_vendor(s, pick_vector_db_placement(s, rag)),
        "guardrails_vendor": pick_guardrails_vendor(s),
        "cicd_vendor": pick_cicd_vendor(s, cicd),
        "observability_vendor": pick_observability_vendor(s, obs),
        "frontend_vendor": pick_frontend_vendor(s, fe),
    }

    # Domain floors run BEFORE exclusions: if the requirement both describes a domain floor (e.g.
    # a CLI tool) AND explicitly excludes something (e.g. "no logging"), the more specific,
    # user-stated exclusion should win the final wording, not the inferred domain default.
    apply_domain_floors(recommendations, s)
    apply_exclusions(recommendations, s)

    return {"signals": s, "recommendations": recommendations}
