#!/usr/bin/env python3
"""
Enrich all technologies in stackKbData with accurate signal_keywords, fix schema inconsistencies, and insert missing technologies.
"""
import json
import re
from pathlib import Path

INDEX_HTML_PATH = Path(__file__).resolve().parents[1] / "index.html"

EXPLICIT_KEYWORDS = {
    "react-ts": ["react", "react.js", "reactjs", "react+ts"],
    "nextjs": ["next.js", "nextjs", "next js"],
    "astro": ["astro", "astro.build"],
    "htmx-hotwire": ["htmx", "hotwire", "turbo"],
    "vaadin-jhipster": ["vaadin", "jhipster"],
    "react-native": ["react native", "react-native"],
    "flutter": ["flutter"],
    "kmp": ["kmp", "kotlin multiplatform"],
    "native-mobile": ["swift", "swiftui", "kotlin android", "jetpack compose"],
    "pwa": ["pwa", "progressive web app"],
    "refine": ["refine.dev", "refine framework"],
    "react-admin": ["react-admin", "react admin"],
    "retool": ["retool"],
    "appsmith": ["appsmith"],
    "tooljet": ["tooljet"],
    "metabase": ["metabase"],
    "spring-boot": ["spring boot", "springboot", "java spring", "spring framework"],
    "dotnet": [".net", "dotnet", "asp.net", "c#", "csharp"],
    "python-fastapi": ["fastapi", "fast api"],
    "camunda-temporal": ["camunda", "temporal", "temporal.io"],
    "rules-engine": ["rules engine", "drools"],
    "buy-cots": ["cots", "off the shelf", "commercial off the shelf"],
    "postgres": ["postgres", "postgresql"],
    "dedicated-vector-db": ["vector db", "vector database"],
    "kafka": ["kafka", "apache kafka"],
    "outbox-pattern": ["outbox pattern", "transactional outbox"],
    "keycloak": ["keycloak"],
    "managed-idp": ["managed idp", "auth as a service"],
    "otel": ["opentelemetry", "otel"],
    "modular-monolith": ["modular monolith"],
    "microservices": ["microservices", "microservice"],
    "python-django": ["django"],
    "nodejs-nest": ["nest.js", "nestjs", "node.js", "nodejs", "node js"],
    "go": ["golang", "go lang", "go language"],
    "php-laravel": ["laravel", "php", "symfony framework"],
    "ruby-rails": ["ruby on rails", "ruby/rails", "rails app", "ruby"],
    "kotlin-backend": ["kotlin", "ktor"],
    "rust": ["rust", "actix", "axum"],
    "elixir-phoenix": ["elixir", "phoenix framework"],
    "scala": ["scala", "akka", "play framework"],
    "cpp": ["c++", "cpp"],
    "c-lang": ["c language", "c lang"],
    "mysql": ["mysql"],
    "mariadb": ["mariadb"],
    "oracle-db": ["oracle database", "oracle db", "oracle sql"],
    "sql-server": ["sql server", "mssql", "microsoft sql server"],
    "db2": ["ibm db2", "db2"],
    "cockroachdb": ["cockroachdb", "cockroach"],
    "yugabytedb": ["yugabyte", "yugabytedb"],
    "aurora": ["aurora", "amazon aurora", "aws aurora"],
    "spanner": ["google spanner", "cloud spanner", "spanner"],
    "sqlite": ["sqlite"],
    "mongodb": ["mongo", "mongodb"],
    "cassandra": ["cassandra", "apache cassandra"],
    "scylladb": ["scylladb", "scylla"],
    "dynamodb": ["dynamodb", "dynamo"],
    "redis": ["redis"],
    "valkey": ["valkey"],
    "couchbase": ["couchbase"],
    "neo4j": ["neo4j"],
    "etcd": ["etcd"],
    "snowflake": ["snowflake"],
    "databricks": ["databricks"],
    "bigquery": ["bigquery", "google bigquery"],
    "redshift": ["redshift", "amazon redshift"],
    "clickhouse": ["clickhouse"],
    "druid": ["apache druid", "druid"],
    "pinot": ["apache pinot", "pinot"],
    "duckdb": ["duckdb"],
    "fabric": ["microsoft fabric", "ms fabric"],
    "iceberg": ["apache iceberg", "iceberg"],
    "delta-lake": ["delta lake", "deltalake"],
    "hudi": ["apache hudi", "hudi"],
    "pgvector": ["pgvector"],
    "qdrant": ["qdrant"],
    "milvus": ["milvus"],
    "weaviate": ["weaviate"],
    "pinecone": ["pinecone"],
    "chroma": ["chromadb", "chroma"],
    "timescaledb": ["timescaledb", "timescale"],
    "influxdb": ["influxdb"],
    "prometheus": ["prometheus"],
    "vue": ["vue", "vue.js", "vuejs"],
    "angular": ["angular"],
    "svelte": ["svelte", "sveltekit"],
    "solid": ["solidjs", "solid.js"],
    "qwik": ["qwik"],
    "alpinejs": ["alpine.js", "alpinejs"],
    "react-router": ["react router"],
    "nuxt": ["nuxt", "nuxtjs", "nuxt.js"],
    "tanstack-start": ["tanstack start", "tanstack"],
    "livewire": ["livewire", "laravel livewire"],
    "liveview": ["liveview", "phoenix liveview"],
    "blazor": ["blazor"],
    "vite": ["vite", "vite.js"],
    "turbopack": ["turbopack"],
    "rspack": ["rspack"],
    "webpack": ["webpack"],
    "esbuild": ["esbuild"],
    "tailwind": ["tailwind", "tailwindcss", "tailwind css"],
    "css-modules": ["css modules"],
    "styled-components": ["styled-components", "styled components"],
    "vanilla-extract": ["vanilla-extract"],
    "tanstack-query": ["react query", "tanstack query"],
    "zustand": ["zustand"],
    "redux-toolkit": ["redux", "redux toolkit", "rtk"],
    "shadcn": ["shadcn", "shadcn/ui", "shadcn ui"],
    "mui": ["material ui", "mui"],
    "antd": ["ant design", "antd"],
    "radix": ["radix ui", "radix"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "oci": ["oci", "oracle cloud"],
    "ibm-cloud": ["ibm cloud"],
    "alibaba-cloud": ["alibaba cloud", "aliyun"],
    "cloudflare": ["cloudflare", "cloudflare workers"],
    "hetzner": ["hetzner"],
    "digitalocean": ["digitalocean", "digital ocean"],
    "fly-io": ["fly.io", "flyio"],
    "railway": ["railway.app", "railway"],
    "render": ["render.com"],
    "vms": ["virtual machines", "ec2", "compute engine", "azure vm"],
    "kubernetes": ["kubernetes", "k8s", "eks", "gke", "aks"],
    "serverless-containers": ["cloud run", "fargate", "container apps", "serverless containers"],
    "faas": ["lambda", "cloud functions", "azure functions", "serverless functions"],
    "paas": ["heroku", "app engine", "elastic beanstalk"],
    "edge-compute": ["edge workers", "edge functions", "lambda@edge"],
    "gateway-api": ["gateway api", "k8s gateway"],
    "ingress-nginx": ["ingress nginx", "nginx ingress"],
    "istio": ["istio"],
    "linkerd": ["linkerd"],
    "cilium": ["cilium", "ebpf"],
    "keda": ["keda"],
    "karpenter": ["karpenter"],
    "sovereign-cloud": ["sovereign cloud", "eu sovereign cloud"],
    "github-actions": ["github actions"],
    "jenkins": ["jenkins"],
    "gitlab-ci": ["gitlab ci", "gitlab-ci", "gitlab pipelines"],
    "azure-pipelines": ["azure devops", "azure pipelines"],
    "circleci": ["circleci", "circle ci"],
    "buildkite": ["buildkite"],
    "argo-workflows": ["argo workflows"],
    "tekton": ["tekton"],
    "dagger": ["dagger.io", "dagger"],
    "argocd": ["argocd", "argo cd"],
    "flux": ["fluxcd", "flux"],
    "spinnaker": ["spinnaker"],
    "harness": ["harness"],
    "terraform": ["terraform"],
    "opentofu": ["opentofu", "tofu"],
    "pulumi": ["pulumi"],
    "aws-cdk": ["aws cdk", "cdk"],
    "crossplane": ["crossplane"],
    "ansible": ["ansible"],
    "sigstore": ["sigstore", "cosign"],
    "slsa": ["slsa"],
    "cyclonedx": ["cyclonedx"],
    "spdx": ["spdx"],
    "renovate": ["renovate", "renovatebot"],
    "dependabot": ["dependabot"],
    "backstage": ["spotify backstage", "backstage"],
    "port": ["getport.io", "port idp"],
    "humanitec": ["humanitec"],
    "okta-workforce": ["okta"],
    "entra-id": ["entra id", "entra", "azure ad", "azure active directory"],
    "ping-identity": ["ping identity", "pingone", "ping federate"],
    "sailpoint": ["sailpoint"],
    "cyberark": ["cyberark"],
    "jumpcloud": ["jumpcloud"],
    "auth0": ["auth0"],
    "cognito": ["aws cognito", "cognito"],
    "entra-external-id": ["entra external id", "azure ad b2c"],
    "ory": ["ory", "ory kratos"],
    "supertokens": ["supertokens"],
    "clerk": ["clerk.dev", "clerk auth", "clerk"],
    "workos": ["workos"],
    "fusionauth": ["fusionauth"],
    "descope": ["descope"],
    "frontegg": ["frontegg"],
    "stytch": ["stytch"],
    "spiffe-spire": ["spiffe", "spire"],
    "vault": ["hashicorp vault", "vault"],
    "openbao": ["openbao"],
    "cert-manager": ["cert-manager"],
    "iam-roles-anywhere": ["iam roles anywhere"],
    "teleport": ["teleport"],
    "oidc": ["oidc", "openid connect"],
    "saml": ["saml", "saml 2.0"],
    "scim": ["scim"],
    "fapi2": ["fapi", "fapi2"],
    "dpop": ["dpop"],
    "mtls": ["mtls", "mutual tls"],
    "verifiable-credentials": ["verifiable credentials", "did"],
    "passkeys": ["passkeys", "webauthn", "fido2"],
    "totp": ["totp", "authenticator app"],
    "push-mfa": ["push mfa", "push notification mfa"],
    "sms-otp": ["sms otp", "sms mfa"],
    "adaptive-auth": ["adaptive auth", "risk-based auth"],
    "opa": ["open policy agent", "opa"],
    "cedar": ["cedar policy", "aws verified permissions"],
    "openfga": ["openfga"],
    "spicedb": ["spicedb", "authzed"],
    "rbac": ["rbac", "role-based access control"],
    "ollama-self-hosted": ["ollama", "self-hosted llm", "local llm"],
    "cloud-api-anthropic": ["anthropic", "claude"],
    "cloud-api-openai": ["openai", "chatgpt"],
    "cloud-api-google": ["google ai", "gemini"],
    "openrouter": ["openrouter"],
    "claude-sonnet": ["claude sonnet", "claude 3.5 sonnet", "sonnet"],
    "openai-gpt-frontier": ["gpt-4o", "gpt-4", "o1", "o3-mini"],
    "gemini-pro": ["gemini pro", "gemini 1.5 pro", "gemini 2.0"],
    "qwen25-family": ["qwen", "qwen 2.5", "qwen2.5"],
    "gemma3-family": ["gemma", "gemma 2", "gemma 3"],
    "mistral-7b": ["mistral", "mixtral", "mistral 7b"],
    "deepseek-coder-distilled": ["deepseek", "deepseek coder", "deepseek-r1"],
}

MISSING_TECHNOLOGIES = [
    {
        "id": "dynatrace",
        "name": "Dynatrace",
        "category": "observability-apm",
        "domain": "observability",
        "surfaces": ["backend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr34"},
        "hiring_pool": "medium",
        "hiring_source_id": "so2025",
        "license": "Proprietary SaaS / Managed",
        "hosting": ["saas", "managed"],
        "exit_cost": "high",
        "tco_shape": "vendor-heavy",
        "best_when": [
            "large enterprise requiring automated full-stack AI root-cause analysis (Davis AI)",
            "hybrid on-prem and multi-cloud legacy enterprise environments"
        ],
        "avoid_when": [
            "early-stage startups with tight opex budgets",
            "cloud-native serverless-only microservices where OpenTelemetry + Grafana suffices"
        ],
        "alternatives": ["datadog", "newrelic", "otel", "prometheus"],
        "innovation_token_cost": 0,
        "signal_keywords": ["dynatrace"]
    },
    {
        "id": "datadog",
        "name": "Datadog",
        "category": "observability-saas",
        "domain": "observability",
        "surfaces": ["backend", "frontend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr34"},
        "hiring_pool": "high",
        "hiring_source_id": "so2025",
        "license": "Proprietary SaaS",
        "hosting": ["saas"],
        "exit_cost": "high",
        "tco_shape": "vendor-heavy",
        "best_when": [
            "fast-moving teams wanting unified turnkey APM, logs, metrics, synthetic testing, and security in one pane",
            "teams without dedicated SRE headcount to self-host observability stacks"
        ],
        "avoid_when": [
            "extreme log/trace volume where unmetered custom metric bills become prohibitive",
            "strict air-gapped on-premise constraints where SaaS egress is forbidden"
        ],
        "alternatives": ["dynatrace", "newrelic", "otel", "prometheus"],
        "innovation_token_cost": 0,
        "signal_keywords": ["datadog"]
    },
    {
        "id": "splunk",
        "name": "Splunk",
        "category": "log-analytics",
        "domain": "observability",
        "surfaces": ["backend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr33"},
        "hiring_pool": "high",
        "hiring_source_id": "so2025",
        "license": "Proprietary / Cisco",
        "hosting": ["saas", "self", "hybrid"],
        "exit_cost": "high",
        "tco_shape": "vendor-heavy",
        "best_when": [
            "enterprise SIEM security compliance and high-volume structured log search",
            "established enterprise SOC security operations"
        ],
        "avoid_when": [
            "lightweight app development seeking cheap distributed tracing"
        ],
        "alternatives": ["elasticsearch", "datadog", "otel"],
        "innovation_token_cost": 0,
        "signal_keywords": ["splunk"]
    },
    {
        "id": "newrelic",
        "name": "New Relic",
        "category": "observability-apm",
        "domain": "observability",
        "surfaces": ["backend", "frontend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr33"},
        "hiring_pool": "medium-high",
        "hiring_source_id": "so2025",
        "license": "Proprietary SaaS",
        "hosting": ["saas"],
        "exit_cost": "medium",
        "tco_shape": "vendor-heavy",
        "best_when": [
            "per-user pricing model fits engineering org structure better than Datadog host-based metering",
            "turnkey full-stack observability with generous free tier"
        ],
        "avoid_when": [
            "teams requiring deep eBPF infrastructure automation"
        ],
        "alternatives": ["datadog", "dynatrace", "otel"],
        "innovation_token_cost": 0,
        "signal_keywords": ["new relic", "newrelic"]
    },
    {
        "id": "elasticsearch",
        "name": "Elasticsearch / ELK Stack",
        "category": "log-analytics",
        "domain": "observability",
        "surfaces": ["backend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr34"},
        "hiring_pool": "very-high",
        "hiring_source_id": "so2025",
        "license": "ELv2 / SSPL / OpenSearch (Apache-2.0)",
        "hosting": ["self", "cloud", "managed"],
        "exit_cost": "medium",
        "tco_shape": "eng-heavy",
        "best_when": [
            "self-hosted log aggregation and full-text search at high volume",
            "avoiding SaaS per-gigabyte log retention costs"
        ],
        "avoid_when": [
            "small teams with zero ops capacity to manage cluster sharding and storage heap"
        ],
        "alternatives": ["splunk", "clickhouse", "otel"],
        "innovation_token_cost": 0,
        "signal_keywords": ["elk stack", "elasticsearch", "opensearch", "elk"]
    },
    {
        "id": "grafana",
        "name": "Grafana",
        "category": "observability-visualization",
        "domain": "observability",
        "surfaces": ["ops", "admin"],
        "maturity": {"ring": "adopt", "source_id": "twr34"},
        "hiring_pool": "very-high",
        "hiring_source_id": "so2025",
        "license": "AGPL-3.0 / Grafana Cloud",
        "hosting": ["self", "saas", "cloud"],
        "exit_cost": "low",
        "tco_shape": "mixed",
        "best_when": [
            "de-facto industry standard for metric dashboards paired with Prometheus, Loki, and Tempo",
            "plugging multiple heterogenous data sources into one unified dashboard"
        ],
        "avoid_when": [
            "teams wanting zero dashboard configuration"
        ],
        "alternatives": ["datadog", "metabase"],
        "innovation_token_cost": 0,
        "signal_keywords": ["grafana", "grafana dashboards"]
    },
    {
        "id": "sonarqube",
        "name": "SonarQube",
        "category": "code-quality-security",
        "domain": "quality",
        "surfaces": ["cicd", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr34"},
        "hiring_pool": "high",
        "hiring_source_id": "so2025",
        "license": "LGPL-3.0 / Commercial Enterprise",
        "hosting": ["self", "saas"],
        "exit_cost": "low",
        "tco_shape": "mixed",
        "best_when": [
            "automated static analysis (SAST), code smell detection, and security quality gates in CI/CD pipelines",
            "enforcing test coverage and maintainability standards across multiple languages"
        ],
        "avoid_when": [
            "lightweight repos that rely purely on fast native linters (e.g. Ruff/Biome/Clippy)"
        ],
        "alternatives": ["github-actions", "renovate"],
        "innovation_token_cost": 0,
        "signal_keywords": ["sonarqube", "sonar", "sonarcloud"]
    },
    {
        "id": "jprofiler",
        "name": "JProfiler",
        "category": "profiling-tools",
        "domain": "observability",
        "surfaces": ["backend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr33"},
        "hiring_pool": "medium",
        "hiring_source_id": "so2025",
        "license": "Commercial Proprietary",
        "hosting": ["local", "self"],
        "exit_cost": "low",
        "tco_shape": "vendor-heavy",
        "best_when": [
            "deep JVM memory leak, CPU bottleneck, thread deadlock, and GC overhead diagnostics",
            "profiling production-grade Java and Kotlin enterprise microservices"
        ],
        "avoid_when": [
            "non-JVM languages (Node, Python, Go, Rust)",
            "continuous production tracing where lightweight APM sampling is preferred"
        ],
        "alternatives": ["visualvm", "otel"],
        "innovation_token_cost": 0,
        "signal_keywords": ["jprofiler"]
    },
    {
        "id": "visualvm",
        "name": "VisualVM",
        "category": "profiling-tools",
        "domain": "observability",
        "surfaces": ["backend", "ops"],
        "maturity": {"ring": "adopt", "source_id": "twr33"},
        "hiring_pool": "high",
        "hiring_source_id": "so2025",
        "license": "GPL-2.0-with-classpath-exception",
        "hosting": ["local"],
        "exit_cost": "low",
        "tco_shape": "eng-heavy",
        "best_when": [
            "free, open-source visual JVM monitoring and heap dump inspection bundled with standard JDK",
            "fast local profiling and live thread sampling during development"
        ],
        "avoid_when": [
            "teams needing advanced multi-JVM telemetry correlation or automated memory leak alerts"
        ],
        "alternatives": ["jprofiler", "otel"],
        "innovation_token_cost": 0,
        "signal_keywords": ["visualvm"]
    }
]


def run():
    html = INDEX_HTML_PATH.read_text(encoding="utf-8")
    m = re.search(r'(<script type="application/json" id="stackKbData">\s*)([\s\S]*?)(\s*</script>)', html)
    if not m:
        raise ValueError("Cannot find stackKbData in index.html")

    kb = json.loads(m.group(2))
    tech_map = {t["id"]: t for t in kb["technologies"]}

    # 1. Update existing technologies with signal_keywords & fix legacy seed data
    for tech in kb["technologies"]:
        tid = tech["id"]
        if tid in EXPLICIT_KEYWORDS:
            tech["signal_keywords"] = EXPLICIT_KEYWORDS[tid]
        elif "signal_keywords" not in tech or not tech["signal_keywords"]:
            name_parts = [p.lower() for p in re.split(r"[\s\-\+\/\(\)]+", tech["name"]) if len(p) > 1]
            tech["signal_keywords"] = [tech["id"], tech["name"].lower()] + name_parts[:2]
            # Deduplicate
            tech["signal_keywords"] = list(dict.fromkeys(tech["signal_keywords"]))

        # Seed data cleanup
        if "license" not in tech:
            tech["license"] = "N/A (Architectural Pattern / Commercial)"
        if not tech.get("avoid_when"):
            tech["avoid_when"] = ["teams with simple static architectures not needing this pattern"]
        if "maturity" in tech and isinstance(tech["maturity"], dict) and "ring" not in tech["maturity"]:
            tech["maturity"]["ring"] = tech["maturity"].get("consensus", "adopt")
            tech["maturity"]["source_id"] = "twr34"

    # 2. Add missing technologies
    for missing in MISSING_TECHNOLOGIES:
        if missing["id"] not in tech_map:
            kb["technologies"].append(missing)
            tech_map[missing["id"]] = missing
            print(f"Added missing tech: {missing['id']}")
        else:
            # Overwrite with clean metadata
            idx = next(i for i, t in enumerate(kb["technologies"]) if t["id"] == missing["id"])
            kb["technologies"][idx] = missing
            print(f"Updated tech: {missing['id']}")

    formatted_json = json.dumps(kb, indent=2, ensure_ascii=False)
    new_html = html[:m.start(2)] + formatted_json + html[m.end(2):]
    INDEX_HTML_PATH.write_text(new_html, encoding="utf-8")
    print(f"Successfully enriched {len(kb['technologies'])} technologies in index.html!")


if __name__ == "__main__":
    run()
