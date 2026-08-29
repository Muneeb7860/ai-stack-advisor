"""POST /api/recommend — Enterprise SaaS Dashboard Recommendation API.

Accepts structured architectural constraints (Product Type, Product Size, Licensed Skills)
and returns an end-to-end technology stack with deterministic fit scores, licensing compliance,
cost estimates, and implementation phases.
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter

from app.rule_engine import recommend_stack
from app.schemas import (
    RecommendRequest,
    RecommendResponse,
    StackCategoryRecommendation,
)

router = APIRouter(prefix="/api", tags=["recommend"])

# Built-in declarative mapping of licenses to technologies
ENTERPRISE_LICENSE_MAP = {
    "postgres_license": {"postgres", "postgresql", "pgvector", "timescale"},
    "postgres_enterprise": {"postgres", "postgresql", "pgvector", "timescale"},
    "redis_enterprise": {"redis", "redis_cluster"},
    "aws_certified_devops": {"aws", "ecs", "fargate", "terraform", "github_actions"},
    "datadog_apm": {"datadog", "apm"},
    "kubernetes_pro": {"kubernetes", "k8s", "eks", "gke"},
    "tensorflow_enterprise": {"tensorflow", "keras", "vllm", "tgi"},
    "snowflake_license": {"snowflake", "sql_analytics"},
    "confluent_kafka": {"kafka", "confluent"},
}

ARCHETYPE_PROMPTS = {
    "b2b_analytics": "High throughput B2B analytics platform with heavy real-time data processing and interactive dashboards.",
    "consumer_mobile": "Fast time-to-market consumer mobile backend with offline-first sync, push notifications, and global CDN.",
    "iot_device": "High ingest IoT device management platform with time-series telemetry, MQTT message brokers, and low-latency alerts.",
    "fintech_realtime": "Strict ACID compliance fintech payment platform with zero-data-loss ledger, mTLS, and audit logging.",
}


@router.post("/recommend", response_model=RecommendResponse)
def generate_recommendation(req: RecommendRequest) -> RecommendResponse:
    # 1. Synthesize requirement query
    base_text = ARCHETYPE_PROMPTS.get(req.product_type, req.product_type)
    scale_text = f"Target scale tier is {req.product_size.upper()} (team headcount {req.team_size or 'standard'})."
    skills_text = f"Licensed team skills available: {', '.join(req.licensed_skills)}." if req.licensed_skills else ""
    extra_text = req.freeform_query or ""

    full_query = f"{base_text} {scale_text} {skills_text} {extra_text}".strip()

    # 2. Run deterministic rule engine
    raw_rec = recommend_stack(full_query)
    raw_picks = raw_rec.get("recommendations", {})

    # Normalize skill keys for license checking
    active_skills = {s.lower().replace(" ", "_").replace("-", "_") for s in req.licensed_skills}
    covered_techs = set()
    for skill in active_skills:
        if skill in ENTERPRISE_LICENSE_MAP:
            covered_techs.update(ENTERPRISE_LICENSE_MAP[skill])

    # 3. Assemble primary category cards
    categories: dict[str, StackCategoryRecommendation] = {}

    # Category mappings: (category_key, display_tech, default_fit, raw_rec_key, alternatives)
    spec_mappings = [
        ("frontend", "React 19 + Next.js 14 App Router", 92, "frontend", ["Vite + React SPA", "SvelteKit 2.0"]),
        ("backend", "Python 3.12 + FastAPI + Pydantic v2", 90, "languages", ["Node.js + NestJS", "Go + Chi"]),
        ("database", "PostgreSQL 16 + pgvector", 94, "database", ["ClickHouse", "TimescaleDB"]),
        ("caching", "Redis 7.2 (Enterprise Cluster)", 88, "cache", ["Dragonfly", "KeyDB"]),
        ("devops", "Terraform + AWS ECS Fargate + GitHub Actions", 86, "compute", ["AWS EKS", "Fly.io"]),
        ("observability", "OpenTelemetry + Prometheus + Grafana Cloud", 91, "observability", ["Datadog", "New Relic"]),
    ]

    total_fit = 0
    covered_count = 0

    for cat_key, fallback_tech, base_fit, raw_key, alts in spec_mappings:
        raw_val = raw_picks.get(raw_key, {})
        tech_name = raw_val.get("v") if isinstance(raw_val, dict) else fallback_tech
        rationale = raw_val.get("why") if isinstance(raw_val, dict) else f"Optimized for {req.product_type} at {req.product_size} scale."

        # Check licensing flag
        tech_lower = (tech_name or "").lower()
        is_covered = any(k in tech_lower for k in covered_techs) or "open_source" in tech_lower or "community" in tech_lower

        if is_covered or not req.licensed_skills:
            lic_status = "COVERED_BY_LICENSE" if is_covered else "COMMUNITY_OPEN_SOURCE"
            lic_flag = "OK"
            covered_count += 1
        else:
            lic_status = "REQUIRES_COMMERCIAL_LICENSE"
            lic_flag = "NEEDS_LICENSE"

        fit = base_fit
        total_fit += fit

        categories[cat_key] = StackCategoryRecommendation(
            technology=tech_name or fallback_tech,
            fit_score=fit,
            license_status=lic_status,
            license_flag=lic_flag,
            rationale=rationale or f"Selected for {req.product_type}.",
            alternatives=alts,
        )

    avg_fit = int(total_fit / len(spec_mappings)) if spec_mappings else 85
    coverage_pct = int((covered_count / len(spec_mappings)) * 100) if spec_mappings else 100

    # Monthly cost estimation based on scale
    cost_ranges = {
        "mvp": (180, 420, 4),
        "smb": (420, 850, 6),
        "enterprise": (1200, 3500, 12),
        "ent": (1200, 3500, 12),
    }
    cost_min, cost_max, weeks = cost_ranges.get(req.product_size, (400, 800, 6))

    action_steps = [
        {
            "step": 1,
            "phase": "Foundation",
            "description": f"Initialize Monorepo with {categories['frontend'].technology} and {categories['backend'].technology}; provision {categories['database'].technology}.",
        },
        {
            "step": 2,
            "phase": "Integration & Caching",
            "description": f"Bind {categories['caching'].technology} layer and configure API authentication gateway.",
        },
        {
            "step": 3,
            "phase": "CI/CD & Observability",
            "description": f"Deploy infrastructure via {categories['devops'].technology} and configure {categories['observability'].technology} telemetry.",
        },
    ]

    return RecommendResponse(
        recommendation_id=f"rec_{uuid.uuid4().hex[:12]}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        input_context={
            "product_type": req.product_type,
            "product_size": req.product_size,
            "team_size": req.team_size,
            "licensed_skills": req.licensed_skills,
            "full_query": full_query,
        },
        overall_metrics={
            "composite_fit_score": avg_fit,
            "licensing_coverage_percent": coverage_pct,
            "estimated_monthly_infra_min": cost_min,
            "estimated_monthly_infra_max": cost_max,
            "time_to_mvp_weeks": weeks,
        },
        stack_categories=categories,
        actionable_next_steps=action_steps,
        raw_recommendations=raw_picks,
    )
