# ML Feature Stores & Model Serving (Traditional ML, not LLM/RAG)

**Status:** implemented — wired into `pickTradeoffs()` via the `mlFeatureStore` signal.

**Domain:** Custom/traditional ML models — recommendation, fraud-scoring, ranking, forecasting —
as distinct from LLM-application architecture, which the rule engine already covers extensively
(`pickLLM`, `pickRAG`, `pickVectorDBPlacement`, etc). Research date: August 2026.

## Business context

A requirement mentioning a custom-trained model (not an LLM prompt/RAG pipeline) — fraud scoring,
personalized ranking, demand forecasting, churn prediction — needs a materially different
infrastructure conversation: training/serving pipelines, feature engineering, and model versioning,
not prompt engineering or vector retrieval.

## Signals / triggers

`recommendation model`, `recommender system`, `fraud scoring`, `fraud detection model`, `risk
scoring model`, `ranking model`, `forecasting model`, `demand forecasting`, `churn model`,
`propensity model`, `custom ML model`, `feature store`, `feature engineering pipeline`, `model
training pipeline`, `model registry`. Explicitly distinct from LLM/RAG signals (`chatbot`, `LLM`,
`RAG`, `prompt`, `embedding search`) already handled elsewhere in this tool — a requirement can
trigger both if it needs an LLM chatbot AND a separate ranking model.

## Decision points

### A. Feature store platform — build vs. buy vs. skip

- **Feast** (open source, Linux Foundation) — flexible, no vendor lock-in, requires significant
  integration effort for online stores/orchestration.
- **Tecton** — managed, strong real-time feature pipelines, higher cost, best for many models
  sharing features at scale.
- **Databricks Feature Store** — tightly coupled to Databricks/Delta Lake.
- **SageMaker Feature Store** — native AWS integration.
- **Decision rule:** a full feature store pays off only once multiple teams share features, you need
  sub-second online serving, and you're fighting real train/serve skew across pipelines. Below that
  threshold, a shared "feature catalog" (versioned code repo) or precomputed features in a normal
  data store is simpler and sufficient — one documented case involved 6 months refactoring an
  over-built custom feature-store deployment that didn't match actual requirements.

### B. Online vs. offline feature serving

Online: Redis, DynamoDB, or Aerospike-backed low-latency stores for point lookups at inference time.
Offline: data warehouse/lakehouse (Snowflake, BigQuery, Delta Lake) for batch training and
backfills. Most feature stores are dual-database systems (offline + online + a sync job) — real
operational overhead; don't add the online path until a product genuinely needs sub-second
freshness.

### C. Model serving infrastructure

- **TorchServe** — PyTorch-native, straightforward for single-framework shops.
- **NVIDIA Triton Inference Server** — multi-framework, GPU-optimized, high-throughput/low-latency
  at scale.
- **KServe / Seldon Core** (on Kubernetes) — standardized, CRD-driven serving with autoscaling,
  canarying, multi-model support; favored by platform teams wanting framework-agnostic, portable
  infra.
- **Cloud-managed endpoints** (SageMaker, Vertex AI) — fastest to production, less operational
  burden, tighter vendor coupling.

### D. Experiment tracking & model registry

**MLflow** (open source, self-hostable) — strong registry + lineage between run → model version →
deployment stage, widely adopted default. **Weights & Biases** — richer collaborative
dashboards/visualization, managed SaaS. The trade-off is largely operational (self-host/open-source
vs. managed/collaboration UX); both solve the "which model version is live" problem raw pickle
files/S3 paths do not.

## Anti-patterns

- **Duplicated feature logic** between training (batch SQL/Spark) and serving (application code) —
  the single biggest cause of training/serving skew.
- **No model registry** — production models tracked via ad hoc file paths or Slack messages, making
  rollback and audit impossible.
- **Premature real-time feature infrastructure** — building a streaming/online feature pipeline for
  a product that only needs daily/hourly freshness adds Kafka/Flink/Redis complexity with no
  user-facing benefit.
- **Over-engineered custom feature store implementations** before requirements justify the
  complexity.
- **Treating a feature store as a silver bullet** — it does not by itself fix skew; the underlying
  transformation code still must be shared/parameterized identically between training and serving
  paths.

## Reference implementations

- **Uber Michelangelo / Palette** — canonical large-scale feature store + model lifecycle platform
  for fraud, ETA, ranking models.
- **Netflix** (Metaflow and internal ML platform) — model lifecycle and feature engineering for
  recommendations.
- **DoorDash, Spotify** — public engineering blogs on feature stores and ranking/forecasting
  platforms.
- **Tecton, Feast (Linux Foundation), Hopsworks** — vendor/OSS reference implementations widely
  benchmarked against each other.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `mlFeatureStore` signal — recommends a full feature store
(Feast/Tecton/SageMaker/Databricks depending on existing platform) only for enterprise/high-scale
profiles; a shared code repo otherwise, plus a standing recommendation to use a model registry
(MLflow) regardless of feature-store maturity.

## Sources

- [Feature Store Comparison 2026: Feast vs Tecton vs Amazon SageMaker Feature Store](https://reintech.io/blog/feature-store-comparison-feast-tecton-sagemaker)
- [You Still Don't Need A Feature Store — Xebia](https://xebia.com/blog/you-still-don-t-need-a-feature-store/)
- [Feature Stores - A Hierarchy of Needs — applyingml.com](https://applyingml.com/resources/feature-stores/)
- [Why Feature Stores Didn't Fix Training–Serving Skew — DEV Community](https://dev.to/synapcores/why-feature-stores-didnt-fix-training-serving-skew-fad)
- [Top Kubernetes-Native Inference Servers Ranked (2026) — HackerNoon](https://hackernoon.com/top-kubernetes-native-inference-servers-ranked-2026)
- [MLflow vs Weights & Biases vs Neptune: Experiment Tracking Compared 2026](https://reintech.io/blog/mlflow-vs-weights-and-biases-vs-neptune-experiment-tracking-comparison)
- [Feature Store: Uncover Uber's Secret to Large Scale Machine Learning — Datagrom](https://www.datagrom.com/data-science-machine-learning-ai-blog/feature-store-uber-ai-large-scale-machine-learning)
- [Lessons on ML Platforms - from Netflix, DoorDash, Spotify, and more — Towards Data Science](https://towardsdatascience.com/lessons-on-ml-platforms-from-netflix-doordash-spotify-and-more-f455400115c7/)
