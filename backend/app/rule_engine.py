"""Python port of the v1 rule engine (index.html's stripNegations()/detectSignals()/pickX()
functions), for use by app/mcp/server.py's recommend_stack() tool.

PORT DISCIPLINE (per the decision already made — see KICKOFF_BRIEF.md and this module's own
kickoff Q&A): this is a faithful transliteration of index.html's JavaScript, not a
re-derivation from first principles. index.html has already been through a validation pass
(see ../validation-report.md) that found and fixed three real bugs — negation handling,
missing on-prem/air-gapped support, and missing data-warehouse detection — plus tightened
team-size and architecture-style conflict handling. index.html's CURRENT source already has
all of those fixes baked in, so porting it as-is (rather than re-implementing the logic from
the PRD/BRD's description of what it *should* do) carries those fixes over automatically.
Do not "clean up" or "simplify" any branch below without checking it against index.html's
actual current logic first — a plausible-looking simplification could silently reintroduce
a bug that was already found and fixed once.

Source of truth: index.html's <script> block, functions stripNegations() through
pickGovernance() (roughly lines 293–830 as of this port). If index.html's rule engine
changes, this file needs the equivalent change — they are two implementations of the same
logic (JS for the zero-backend v1 product, Python for the MCP tool), not one importing the
other, since v1 must stay a fully client-side, zero-backend product (PRD NFR-1/NFR-5).

Naming: JS object keys (camelCase, e.g. `s.onPrem`) are kept AS-IS in the `signals` dict
returned by detect_signals() — not snake_cased — specifically so this stays a mechanical,
diffable port against index.html rather than introducing a naming translation layer that
could hide a transcription error. Function/module names are snake_case per Python
convention; signal dict keys are not.
"""
import re

# ---------- Signal detection ----------


def strip_negations(text: str) -> str:
    """Strip short negated clauses ("no document search", "don't have compliance requirements
    yet") before keyword matching, so stated non-requirements don't get read as requirements.
    Mirrors index.html's stripNegations() exactly, including the same 60-char clause cap."""
    return re.sub(
        r"\b(no|not|without|don't|doesn't|isn't|won't|never|excluding|except for|except)\b"
        r"[^.,;!?]{0,60}",
        " ",
        text,
        flags=re.IGNORECASE,
    )


def detect_signals(text: str) -> dict:
    """Mirrors index.html's detectSignals() exactly. `raw` is used only for phrases that are
    themselves phrased with "no"/"cannot" — the negation IS the requirement there (on-prem
    detection), same comment as the JS source."""
    raw = text.lower()
    t = strip_negations(text).lower()

    def has(words):
        return any(w in t for w in words)

    def has_raw(words):
        return any(w in raw for w in words)

    # "on-prem" alone is ambiguous with a hybrid setup that explicitly also mentions cloud
    # ("hybrid on-prem and cloud systems") — only the unambiguous air-gapped/no-cloud phrasings
    # should override regardless of nearby "hybrid"/"cloud" wording.
    strong_on_prem = has_raw(
        [
            "air-gapped", "air gapped", "airgapped", "cannot use any public cloud",
            "no public cloud", "private cloud only", "bare metal deployment",
        ]
    )
    soft_on_prem = has_raw(["on-prem", "on premises", "on-premise"]) and not (
        has_raw(["hybrid"]) and has_raw(["cloud"])
    )

    return {
        "onPrem": strong_on_prem or soft_on_prem,
        "healthcare": has(["health", "hipaa", "patient", "clinical", "ehr", "medical"]),
        "finance": has(
            ["fintech", "bank", "payment", "fraud", "pci", "transaction", "trading", "ledger", "finance"]
        ),
        "ecommerce": has(
            ["ecommerce", "e-commerce", "retail", "shopping", "product recommendation", "cart", "checkout"]
        ),
        "enterprise": has(
            [
                "enterprise", "large organization", "corporate", "multi-region",
                "audit logging", "role-based access", "okta", "sso",
            ]
        ),
        "startupMvp": has(
            [
                "startup", "mvp", "early-stage", "small team", "move fast",
                "budget conscious", "budget-conscious", "bootstrapped",
            ]
        ),
        "highScale": has(
            ["high traffic", "high volume", "high transaction", "scale", "millions of users", "peak load", "sales event", "black friday"]
        ),
        "realtime": has(["real-time", "real time", "low latency", "streaming", "live"]),
        "chatbot": has(["chatbot", "conversational", "customer support bot", "assistant", "virtual agent"]),
        "knowledgeBase": has(
            ["knowledge base", "internal documents", "policy documents", "confluence", "wiki", "document search", "faq"]
        ),
        "agentic": has(
            ["agentic", "multi-agent", "take actions", "automate workflow", "autonomous", "tool use", "function calling"]
        ),
        "mobile": has(["mobile", "flutter", "ios", "android", "react native"]),
        "web": has(["web app", "website", "web application", "react", "angular", "vue"]),
        "voice": has(["voice", "speech", "call center", "ivr"]),
        "compliance": has(["soc2", "hipaa", "pci", "gdpr", "compliance", "regulated", "audit"]),
        "security": has(["security", "pii", "sensitive data", "encryption", "zero trust"]),
        "dataHeavy": has(["big data", "analytics", "data pipeline", "data lake", "etl", "warehouse"]),
        "structured": has(["structured data", "relational", "transactional", "sql", "ledger", "orders"]),
        "unstructured": has(["unstructured", "documents", "pdf", "images", "logs", "text data"]),
        "iot": has(["iot", "sensor", "device telemetry", "edge device"]),
        "awsShop": has(["aws", "amazon web services"]),
        "azureShop": has(["azure", "microsoft"]),
        "gcpShop": has(["gcp", "google cloud"]),
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
        "privilegedAccess": has(
            ["privileged access", "pam ", "vaulting", "session recording", "admin credential", "privileged account"]
        ),
        "identityGovernance": has(
            ["identity governance", "access certification", "access review", "segregation of duties", "sod ", "iga "]
        ),
        "deviceMgmt": has(["device management", "mdm", "mac-heavy", "mostly macs", "byod", "endpoint management"]),
        # Word-boundary + negative-lookahead: plain " java" would also match inside " javascript".
        "javaMentioned": bool(re.search(r"\bjava\b(?!script)", t, re.IGNORECASE)),
        "pythonMentioned": has(["python"]),
        # Avoid matching the common English word "go" (e.g. "go live", "let's go fast") —
        # only count it when phrased as the language (golang, "go lang", "written/using in Go").
        "goMentioned": (
            has(["golang"])
            or bool(re.search(r"\bgo\s*(lang|language)\b", t))
            or bool(re.search(r"\b(written in|using|in)\s+go\b", t))
        ),
        "smallTeam": (
            has(
                [
                    "small team", "2 engineers", "3 engineers", "4 engineers", "5 engineers",
                    "6 engineers", "solo founder", "few engineers",
                ]
            )
            or bool(re.search(r"\b([1-9]|1[0-2])[- ]?(person|people)\b", t))
            or bool(re.search(r"team of\s*([1-9]|1[0-2])\b", t))
        ),
        "largeTeam": has(["large team", "many teams", "multiple teams", "platform team"]),
        "globalMultiRegion": has(["global", "multi-region", "worldwide", "international"]),
        "search": has(["search engine", "semantic search", "recommendation"]),
        "email": has(["email drafting", "email assistant", "draft email"]),
        "ragNeed": has(
            [
                "knowledge base", "document search", "internal documents", "confluence",
                "faq", "clinical knowledge", "policy documents", "search across",
            ]
        ),
    }


# ---------- Category logic ----------


def pick_cloud(s):
    if s["onPrem"]:
        return {
            "v": "On-premises / private infrastructure — no public cloud",
            "why": "An air-gapped or explicit no-public-cloud requirement rules out AWS/Azure/GCP entirely. You need a private data center, bare-metal, or air-gapped virtualization stack (VMware, OpenStack, or a vetted sovereign/government enclave) instead.",
            "conf": "high",
        }
    if s["awsShop"]:
        return {
            "v": "AWS",
            "why": "Explicit AWS usage detected — build on existing footprint (IAM, VPC, billing) rather than introducing a second cloud.",
            "conf": "high",
        }
    if s["gcpShop"] or s["agentic"]:
        return {
            "v": "Google Cloud (GCP)",
            "why": "GCP mentioned, or agentic/data-heavy workload — GCP pairs well with Vertex AI, BigQuery, and Gemini models.",
            "conf": "high" if s["gcpShop"] else "medium",
        }
    if s["azureShop"] or s["enterprise"]:
        return {
            "v": "Microsoft Azure",
            "why": "Azure mentioned, or enterprise context with likely existing Microsoft 365/AD investment.",
            "conf": "high" if s["azureShop"] else "medium",
        }
    if s["startupMvp"]:
        return {
            "v": "AWS (or GCP)",
            "why": "Broadest managed-service catalog and hiring pool for a small team moving fast; GCP is a fine alternative if the team is more data/ML-leaning.",
            "conf": "medium",
        }
    return {
        "v": "AWS",
        "why": "Default choice given broadest ecosystem maturity; revisit if there is an existing cloud commitment.",
        "conf": "low",
    }


def pick_gateway(s):
    if s["onPrem"]:
        return {
            "v": "Internal API gateway (Kong or Apigee Edge on-prem, or NGINX/Envoy) — no public CDN/edge service",
            "why": "Cloudflare and similar public edge services require internet egress, which an air-gapped environment doesn't have. Run your gateway entirely inside the isolated network boundary.",
            "conf": "high",
        }
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
    return {
        "v": " + ".join(picks),
        "why": "Cloudflare handles edge security/performance; Apigee (if present) adds API productization and governance for many external consumers.",
        "conf": "high" if hits >= 2 else "medium" if hits == 1 else "low",
    }


# Identity-provider landscape beyond Okta. Sourced/grounded against published vendor
# comparisons (lumos.com/identity-matters) as of mid-2026 — pricing moves fast in this
# market, so treat $ figures as directional, not quoted. IMPORTANT categorization note baked
# into the logic below: CyberArk (PAM), SailPoint/Saviynt (IGA) are NOT drop-in Okta
# replacements — they solve different problems and are usually layered ON TOP of an IdP, not
# instead of one — pick_iam() returns them as a separate "complementary" list. OWNERSHIP
# NOTE: Thoma Bravo owns Ping, SailPoint, and the former ForgeRock — cross-shopping those
# three specifically doesn't create the independent competitive pressure it looks like.
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
]

# Curated from lumos.com/identity-matters "Identity and access management metrics" — full
# source article lists ~19; these 8 are the highest-signal set for a first-draft target sheet.
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

# Curated from lumos.com/identity-matters "IAM/RBAC best practices" (12 in the source article).
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
    if not picks:
        picks.append("Python (FastAPI) for AI-heavy services, Java (Spring Boot) or Go for core backend")
    return {
        "v": " · ".join(picks),
        "why": "Split by workload: Java/Go for performance-critical transactional paths, Python for AI/ML and RAG pipelines where the ecosystem (LangChain, LlamaIndex, etc.) lives.",
        "conf": "high" if hits >= 1 else "medium" if picks else "low",
    }


def pick_architecture(s):
    # Team size is the primary driver of monolith-vs-microservices (Conway's law) — a 3-person
    # team shouldn't run real microservices even if compliance/enterprise needs are also
    # present; those needs are served by governance practices, not service-decomposition granularity.
    if s["startupMvp"] or s["smallTeam"]:
        why = "Small teams move faster with one deployable unit; hexagonal internal layering keeps a future microservices split cheap."
        if s["enterprise"] or s["compliance"]:
            why += " Compliance/enterprise requirements are met through governance practices (audit logging, strict domain boundaries, IAM) inside this monolith, not by splitting into services your team is too small to operate."
        return {"v": "Modular monolith (hexagonal internal structure), split into microservices later", "why": why, "conf": "high"}
    if s["enterprise"] or s["largeTeam"]:
        return {"v": "Microservices with Hexagonal (Ports & Adapters) architecture", "why": "Enterprise scale and multiple teams benefit from independent deployability and clean domain boundaries isolated from infrastructure concerns.", "conf": "high"}
    return {"v": "Microservices, hexagonal per bounded context", "why": "Balances scalability with maintainability for a mid-size team and domain.", "conf": "low"}


def pick_compute(s):
    if s["onPrem"]:
        return {"v": "Self-managed Kubernetes on bare metal/VMware — no public-cloud serverless", "why": "Serverless compute (Lambda/Cloud Run) is a public-cloud managed service and isn't available air-gapped/on-prem — self-managed Kubernetes (or a simpler container orchestrator) inside your isolated network is the realistic option.", "conf": "high"}
    if (s["startupMvp"] or s["smallTeam"]) and (s["highScale"] or s["enterprise"] or s["realtime"]):
        return {"v": "Serverless containers (Cloud Run / Fargate) with autoscaling", "why": "Small team and real-time/high-scale/enterprise needs pull in different directions here — managed serverless containers give real autoscaling and container-level control without the ops burden of running your own Kubernetes cluster. Move to full self-managed Kubernetes only once you have dedicated platform engineering capacity.", "conf": "medium"}
    if s["startupMvp"] or (s["smallTeam"] and not s["highScale"]):
        return {"v": "Serverless (Cloud Run / Lambda / Cloud Functions)", "why": "Minimal ops overhead, pay-per-use, ideal for small teams and unpredictable early-stage traffic.", "conf": "high"}
    if s["highScale"] or s["enterprise"] or s["realtime"]:
        return {"v": "Kubernetes (containers) with autoscaling", "why": "Predictable performance, fine-grained resource control, and portability needed at scale or for latency-sensitive workloads.", "conf": "high"}
    return {"v": "Hybrid: serverless for bursty/event-driven work, Kubernetes for core always-on services", "why": "Use the right compute per workload rather than one-size-fits-all.", "conf": "low"}


def pick_messaging(s):
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
        picks.append("Kafka for event streaming, Redis for pub/sub-style ephemeral messaging")
    return {
        "v": " · ".join(picks),
        "why": "Kafka for durable, replayable event streams (audit, fraud, analytics); lighter managed queues when volume/ops budget don't justify Kafka yet.",
        "conf": "high" if hits >= 2 else "medium" if hits == 1 else "low",
    }


def pick_mesh(s):
    if s["enterprise"] or s["largeTeam"]:
        return {"v": "Istio", "why": "Multiple services/teams benefit from mTLS, traffic shaping, and observability at the mesh layer.", "conf": "medium"}
    return {"v": "Not needed yet (revisit past ~10-15 services)", "why": "Service mesh adds operational complexity; skip until service count and cross-team traffic policy needs justify it.", "conf": "medium"}


def pick_cache(s):
    return {"v": "Redis", "why": "De facto standard for caching, session storage, rate limiting, and lightweight pub/sub — recommended almost universally.", "conf": "high"}


def pick_database(s):
    picks = []
    hits = 0
    # Analytics/ETL/reporting-centric workload with no transactional/chat/RAG signal = a
    # warehouse question, not an OLTP-database question.
    warehouse_need = s["dataHeavy"] and not s["structured"] and not s["chatbot"] and not s["ragNeed"]
    if warehouse_need:
        picks.append("Cloud data warehouse (BigQuery / Snowflake / Redshift) as the analytics store")
        hits += 1
    if s["structured"] or s["finance"] or (not s["unstructured"] and not warehouse_need):
        picks.append("PostgreSQL (primary transactional store)")
        if s["structured"] or s["finance"]:
            hits += 1
    if s["unstructured"] or s["chatbot"] or s["ragNeed"]:
        picks.append("MongoDB (flexible schema for content, chat history, documents)")
        if s["unstructured"]:
            hits += 1
    if s["iot"] or (s["highScale"] and s["dataHeavy"]):
        picks.append("Cassandra (write-heavy, high-scale, multi-region time-series/event data)")
        hits += 1
    if not picks:
        picks.append("PostgreSQL as primary store")
    why = (
        "Your workload reads as analytics/ETL/reporting-centric rather than transactional — a columnar cloud warehouse is built for exactly that (large scans, aggregations, BI-tool integration), which Postgres/Mongo/Cassandra are not optimized for. Add Postgres alongside it only if you also have an operational/transactional app component; add Cassandra alongside it if you also have high-volume write ingestion (e.g. IoT/event streams) feeding the warehouse."
        if warehouse_need
        else "Postgres for relational/transactional integrity, MongoDB for flexible document data, Cassandra only when write volume and multi-region needs exceed what Postgres/Mongo comfortably handle."
    )
    return {"v": " · ".join(picks), "why": why, "conf": "high" if hits >= 1 else "medium"}


def pick_containers(s):
    if s["onPrem"]:
        return {"v": "Docker + self-managed Kubernetes (kubeadm/Rancher/RKE2 on bare metal or VMware) — not EKS/GKE/AKS", "why": "Managed Kubernetes offerings are public-cloud services; an air-gapped/on-prem environment needs a self-managed distribution you can run entirely inside your network boundary.", "conf": "high"}
    if s["startupMvp"]:
        return {"v": "Docker + managed serverless containers (Cloud Run / Fargate)", "why": "Keep container benefits without managing a Kubernetes control plane.", "conf": "high"}
    return {"v": "Docker + Kubernetes (EKS/GKE/AKS matching chosen cloud)", "why": "Standard for portable, scalable container orchestration once team/scale justify it.", "conf": "high" if (s["enterprise"] or s["highScale"]) else "medium"}


def pick_observability(s):
    if s["onPrem"]:
        return {"v": "OpenTelemetry (instrumentation standard) + self-hosted Grafana + Prometheus + Loki (or ELK/OpenSearch)", "why": "SaaS observability platforms (Datadog, Splunk Cloud, Dynatrace SaaS) require sending telemetry to the vendor's cloud, which an air-gapped network can't reach — self-hosted OSS observability is the only realistic option inside the boundary.", "conf": "high"}
    apm = "Datadog"
    why = "Best all-around breadth (APM, logs, infra, RUM) with fastest time-to-value."
    conf = "low"
    if s["enterprise"] and s["compliance"]:
        apm = "Splunk (+ Datadog or Dynatrace for APM)"
        why = "Enterprises with heavy compliance/audit needs often standardize log management on Splunk alongside a dedicated APM tool."
        conf = "high"
    elif s["enterprise"] and s["highScale"]:
        apm = "Dynatrace"
        why = "Strong automatic root-cause analysis (AI-assisted) valuable at large, complex enterprise scale."
        conf = "high"
    elif s["startupMvp"]:
        apm = "Grafana + Prometheus (OSS) or Datadog free tier"
        why = "Lower cost for a small team; upgrade to Datadog/Dynatrace as scale and budget grow."
        conf = "medium"
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
    return {
        "v": " + ".join(picks),
        "why": "React for fastest ecosystem/hiring fit (Angular if already an enterprise Angular shop); Flutter when both iOS and Android are needed from one codebase.",
        "conf": "high" if hits >= 1 else "low",
    }


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
    if s["onPrem"]:
        return {"v": "Self-hosted GitLab CE or Jenkins with self-hosted runners, deploying via Terraform to your private infrastructure", "why": "Cloud-hosted CI/CD (GitHub Actions cloud runners, Vercel) needs internet connectivity to reach your infrastructure — an air-gapped environment needs the entire pipeline, including runners, inside the network boundary.", "conf": "high"}
    if s["startupMvp"]:
        return {"v": "GitHub Actions → Vercel (frontend) + Cloud Run/Fargate (backend)", "why": "Fastest path to production for a small team, minimal infra to manage.", "conf": "high"}
    if s["enterprise"]:
        return {"v": "GitHub Actions/GitLab CI → ArgoCD (GitOps) → Kubernetes, Terraform for infra-as-code", "why": "GitOps gives auditable, repeatable deployments at enterprise scale with multiple environments/teams.", "conf": "high"}
    return {"v": "GitHub Actions → Terraform + Kubernetes (or Vercel for frontend-only pieces)", "why": "Balanced CI/CD with infra-as-code as the team and service count grow.", "conf": "low"}


def pick_dns(s):
    if s["onPrem"]:
        return {"v": "Internal DNS (BIND / Windows DNS / private zone) — no public DNS provider", "conf": "high"}
    if s["awsShop"]:
        return {"v": "Route 53 (AWS-native, integrates with ALB/CloudFront)", "conf": "high"}
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
        {"task": "Architecture / system design & complex multi-step reasoning", "model": "Frontier large model (Claude Opus/Sonnet, GPT-5/o-series, Gemini Pro)", "why": "These calls are low-volume and high-stakes — the cost premium is trivial against the value of a correct design decision, and deep reasoning quality drops off fastest on smaller models."},
        {"task": "Code generation, review & refactoring", "model": "Mid-large code-tuned model (Claude Sonnet, GPT-4.1-class, DeepSeek-Coder-V2, Codestral)", "why": "Strong code benchmarks at meaningfully lower cost/latency than reserving your top-tier reasoning model for every completion."},
        {"task": "Classification, extraction, routing, simple chat", "model": "Small open-weight model, 4B–12B (Gemma, Llama, DeepSeek-small, Phi)", "why": "High call volume, low per-call complexity — this is where model cost dominates total spend, so the cheapest model that clears the quality bar wins. Also the tier most worth self-hosting."},
        {"task": "RAG answer synthesis", "model": "Mid-size model, 12B–30B", "why": "Needs enough reasoning capacity to stay grounded in retrieved context without hallucinating, but doesn't need frontier-level general reasoning."},
        {"task": "Agent orchestration / multi-step tool-use", "model": "Frontier or a tool-use-specialized large model", "why": "Reliability of tool-call formatting and multi-step planning degrades noticeably on smaller models — this is the task type least tolerant of downgrading."},
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


VRAM_TABLE = [
    {"tier": "4B (small)", "fp16": "~8–10 GB", "int4": "~4–6 GB", "gpu": "Single consumer/edge GPU — RTX 4090 (24GB), L4 (24GB), or smaller", "notes": "Comfortable single-GPU deployment even with room for concurrent requests and moderate context length."},
    {"tier": "12B (small-mid)", "fp16": "~24–28 GB", "int4": "~10–14 GB", "gpu": "L4 (24GB) or RTX 4090 (24GB) quantized; A10G (24GB) fp16 is tight", "notes": "Int4 quantization is the practical default here to keep single-GPU deployment comfortable with headroom for KV-cache."},
    {"tier": "30B (mid-large)", "fp16": "~60–65 GB", "int4": "~18–22 GB", "gpu": "A100 40GB (quantized) or A100/H100 80GB (fp16) for headroom", "notes": "This is where quantization stops being optional for single-GPU deployment — budget for it unless you have an 80GB card."},
    {"tier": "70B+ (large)", "fp16": "~140+ GB", "int4": "~38–45 GB", "gpu": "Multi-GPU (2–4× A100/H100) for fp16, or a single H100 80GB with aggressive quantization", "notes": "Multi-GPU tensor-parallel serving adds real operational complexity — this tier is usually where \"just use a cloud API for this size\" wins on total cost of ownership unless you have a hard data-residency reason not to."},
]


def pick_vram_tier(s):
    if (s["compliance"] or s["healthcare"] or s["security"]) and s["enterprise"]:
        return {"tier": "30B (mid-large)", "why": "Fully local deployment for regulated data needs enough model capacity to approach cloud-frontier quality; 30B-class open-weight models are the current sweet spot for that trade-off before multi-GPU complexity kicks in at 70B+."}
    if s["dataHeavy"] or s["ragNeed"]:
        return {"tier": "12B (small-mid)", "why": "RAG-heavy workloads benefit from a bit more reasoning capacity than the smallest tier for staying grounded in retrieved context, without paying 30B's VRAM/GPU cost."}
    return {"tier": "4B (small)", "why": "For routing/classification/extraction-style local workloads, the smallest tier that clears your quality bar minimizes both VRAM footprint and per-request latency — start here and size up only if evals show it's insufficient."}


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

    return {"glossary": glossary, "llm": llm, "rag": rag}


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

    # 0. On-prem overrides the whole cloud-strategy question
    if s["onPrem"]:
        t.append({"d": "Public cloud vs. On-premises", "rec": "On-premises / air-gapped private infrastructure", "why": "An explicit no-public-cloud / air-gapped requirement overrides the usual cloud trade-off entirely — this isn't a single-vs-multi-cloud decision, it's a build-and-operate-your-own-infrastructure decision.", "when": "Revisit only if the air-gap/no-public-cloud constraint is ever relaxed (e.g. a sovereign/government cloud region becomes an approved option).", "conf": "high"})
    # 1. Single-cloud vs multi-cloud
    elif s["enterprise"] and s["globalMultiRegion"] and s["compliance"]:
        t.append({"d": "Single-cloud vs. Multi-cloud", "rec": "Primary cloud + a scoped secondary cloud (DR / regulatory only)", "why": "Global, regulated, enterprise-scale profile — data-residency law or contractual disaster-recovery requirements often force a second cloud presence, but that's different from running everything active-active across two clouds.", "when": "Go further into full multi-cloud only if you have multiple regions with hard data-sovereignty laws requiring in-country cloud presence, or a board-level mandate to avoid single-vendor concentration risk regardless of cost.", "conf": "medium"})
    else:
        t.append({"d": "Single-cloud vs. Multi-cloud", "rec": "Single cloud", "why": "Multi-cloud roughly doubles operational complexity — two IAM models, two networking stacks, two sets of managed services to learn and monitor — for a benefit (vendor leverage, avoiding lock-in) that rarely pays off before significant scale.", "when": "Reconsider if a single-vendor outage has caused a business-critical incident more than once, procurement specifically wants renewal leverage, or compliance mandates in-country presence your primary cloud can't offer.", "conf": "high"})

    # 2. IaC tool
    if s["pythonMentioned"] and not s["awsShop"]:
        t.append({"d": "Terraform vs. Pulumi vs. native IaC", "rec": "Terraform, with Pulumi as a strong alternative given your Python usage", "why": "Terraform remains the safest default — largest module ecosystem, cloud-agnostic, easiest to hire for. Pulumi is worth it specifically because it lets your existing Python team write infra in a real language (loops, conditionals, unit tests) instead of HCL.", "when": "Pick Pulumi over Terraform if your team already writes Python/TypeScript daily and wants infra code reviewed and tested the same way as application code. Pick cloud-native IaC (CDK, Bicep, Deployment Manager) only if you are firmly single-cloud and want zero third-party tooling in the deploy path.", "conf": "medium"})
    elif s["awsShop"] and s["startupMvp"]:
        t.append({"d": "Terraform vs. AWS CDK vs. native IaC", "rec": "Terraform as the default; AWS CDK is a reasonable alternative for an AWS-only small team", "why": "Terraform is cloud-agnostic and keeps optionality if you ever add a second cloud or need to hire from the broader IaC talent pool. CDK gives tighter day-one AWS service coverage and lets you write infra in TypeScript/Python, at the cost of being AWS-only.", "when": "Choose CDK specifically if you're confident you'll stay AWS-only long-term and want less HCL to learn. Move to Terraform (or add it) the moment a second cloud or a Terraform-experienced hire enters the picture.", "conf": "medium"})
    else:
        t.append({"d": "Terraform vs. other IaC", "rec": "Terraform", "why": "Industry-standard, cloud-agnostic, declarative IaC with the largest module ecosystem and community support — the safest long-term default for hiring, documentation, and multi-cloud optionality.", "when": "Reconsider only if your team is deeply invested in a general-purpose language (Python/TypeScript/Go) and wants Pulumi's programmatic style, or you are permanently single-cloud and want to drop third-party tooling in favor of native IaC (CloudFormation/Bicep/Deployment Manager).", "conf": "medium"})

    # 3. Kafka vs Pub/Sub vs managed queue
    if s["highScale"] or s["realtime"] or s["finance"]:
        t.append({"d": "Kafka vs. Pub/Sub vs. managed queue (SQS/SNS)", "rec": "Kafka", "why": "You need a durable, replayable log — required for audit trails, fraud/analytics pipelines, high sustained throughput, or multiple independent consumer groups reading the same stream at different speeds. Managed queues don't give you replay or that throughput ceiling.", "when": "Downgrade to a managed queue (SQS/Pub/Sub) if it turns out you don't actually need replay/audit history and traffic is moderate — Kafka's operational cost (self-managed or Confluent/MSK bill) only pays off once you're using its durability and replay guarantees.", "conf": "high"})
    elif s["gcpShop"]:
        t.append({"d": "Kafka vs. Pub/Sub vs. managed queue (SQS/SNS)", "rec": "Google Pub/Sub", "why": "Fully managed, zero ops, integrates natively with the rest of a GCP stack. The right choice when you don't yet have Kafka-specific needs like event replay, ultra-high sustained throughput, or complex multi-consumer-group patterns.", "when": "Move to Kafka (Confluent Cloud or self-managed on GKE) once you need event replay for audit, multiple independent consumer groups at different read speeds, or throughput/latency Pub/Sub can't guarantee at your scale.", "conf": "high"})
    else:
        t.append({"d": "Kafka vs. Pub/Sub vs. managed queue (SQS/SNS)", "rec": "Managed queue (SQS/Pub/Sub) first; adopt Kafka only when you outgrow it", "why": "Start with the lowest-ops option. Introducing a Kafka cluster before you actually need its guarantees just adds infrastructure to operate for no measurable benefit.", "when": "Move to Kafka when you need: event replay/audit trail, multiple consumer groups reading the same stream at different speeds, sustained throughput above roughly 10k messages/sec, or you're building a real event-sourcing/CDC pipeline.", "conf": "medium"})

    # 4. Kubernetes vs Serverless — mirrors pick_compute()'s branch order exactly so this
    # trade-off card never contradicts the Compute Model card for the same signals.
    if (s["startupMvp"] or s["smallTeam"]) and (s["highScale"] or s["enterprise"] or s["realtime"]):
        t.append({"d": "Kubernetes vs. Serverless", "rec": "Serverless containers (Cloud Run / Fargate) — middle path", "why": "Small team and real-time/high-scale/enterprise needs pull in different directions: full self-managed Kubernetes is more operational overhead than your team can likely absorb, but plain serverless functions under-deliver on control at this scale. Managed serverless containers give autoscaling and container-level control without a Kubernetes control plane to operate.", "when": "Move to full self-managed Kubernetes once you have dedicated platform engineering capacity; fall back to plain serverless functions if scale/latency needs turn out lighter than described.", "conf": "medium"})
    elif s["startupMvp"] or (s["smallTeam"] and not s["highScale"]):
        t.append({"d": "Kubernetes vs. Serverless", "rec": "Serverless (Cloud Run / Lambda / Cloud Functions)", "why": "No cluster to operate, patch, or right-size; you pay only for what you use, which matches a small team's time budget and an early-stage product's unpredictable traffic.", "when": "Move to Kubernetes once you have many services with complex inter-service networking needs, need fine-grained resource/cost control at steady high load, or serverless cold-start latency becomes a measurable user-facing problem.", "conf": "high"})
    elif s["highScale"] or s["enterprise"] or s["realtime"]:
        t.append({"d": "Kubernetes vs. Serverless", "rec": "Kubernetes", "why": "Predictable performance under sustained load, fine-grained resource control, and portability across clouds — worth the operational overhead once you're running many services at real scale or have strict latency SLAs serverless cold-starts would violate.", "when": "Fall back to serverless for individual bursty/event-driven workloads even inside a Kubernetes-centric org (e.g. scheduled jobs, webhooks) — it's not all-or-nothing per service.", "conf": "high"})

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


def pick_concurrency(s):
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
    return items


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


# ---------- Top-level entry point ----------


def recommend_stack(requirement_text: str) -> dict:
    """Mirrors index.html's analyze() function: runs the full rule engine over a free-text
    requirement and returns {signals, recommendations}. This is the single function
    app/mcp/server.py's recommend_stack() tool calls — everything above is private to this
    module. Category keys are snake_case (this is server-side Python, not a mechanical port
    of index.html's rendering code) — only the signal dict keys stay camelCase, per this
    module's docstring."""
    if not requirement_text or not requirement_text.strip():
        raise ValueError("requirement_text must be non-empty")

    s = detect_signals(requirement_text)

    rag = pick_rag(s)

    recommendations = {
        "cloud": pick_cloud(s),
        "gateway": pick_gateway(s),
        "iam": pick_iam(s),
        "languages": pick_languages(s),
        "architecture": pick_architecture(s),
        "compute": pick_compute(s),
        "messaging": pick_messaging(s),
        "mesh": pick_mesh(s),
        "cache": pick_cache(s),
        "database": pick_database(s),
        "containers": pick_containers(s),
        "observability": pick_observability(s),
        "frontend": pick_frontend(s),
        "cicd": pick_cicd(s),
        "dns": pick_dns(s),
        "docs": pick_docs(s),
        "llm": pick_llm(s),
        "mcp_servers": pick_mcp(s),
        "rag": rag,
        "guardrails": pick_guardrails(s),
        "cost_optimization": pick_cost_optimization(s),
        "concurrency": pick_concurrency(s),
        "governance": pick_governance(s),
        "tradeoffs": pick_tradeoffs(s),
        "model_orchestration": pick_model_orchestration(s),
        "hosting_location": pick_hosting_location(s),
        "vram_tier": pick_vram_tier(s),
        "interface_topology": pick_interface_topology(s),
        "mcp_vs_api": pick_mcp_vs_api(s),
        "guardrail_pipeline": pick_guardrail_pipeline(s),
        "vector_db_placement": pick_vector_db_placement(s, rag),
    }

    return {"signals": s, "recommendations": recommendations}
