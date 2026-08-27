# Search & Recommendation Engine

**Status:** implemented — wired into `pickTradeoffs()` via the `searchRecommendation` signal.

**Domain:** Product/content search and discovery — as a general capability distinct from LLM-based
RAG semantic search, though hybrid search connects the two. Research date: August 2026.

## Business context

Relevant for any product with a search box, catalog browsing, or a "recommended for you"/discovery
surface — a general capability many products need regardless of whether they also have an LLM
chatbot. This document is deliberately scoped to classic search/recsys, cross-referencing (not
duplicating) the existing RAG/vector-DB reasoning already in the tool for LLM-application semantic
search.

## Signals / triggers

Search-oriented: `search bar`, `search box`, `product search`, `site search`, `search relevance`,
`typo tolerance`, `autocomplete`, `instant search`, `faceted search`, `filters`, `full-text search`.
Discovery/recommendation-oriented: `recommendations`, `recommended for you`, `you may also like`,
`personalized feed`, `for you page`, `discovery`, `similar items`, `related products`, `trending`,
`cold start`, `collaborative filtering`, `content-based`, `ranking model`, `feed algorithm`.

## Decision points

### A. Search index technology

- **Elasticsearch** — richest relevance/analytics feature set, mature ecosystem, but SSPL/Elastic
  License 2.0 (restricts hosted-cloud resale) and heavy ops burden (JVM, shard management). Best
  for multi-terabyte catalogs needing deep analytics alongside search.
- **OpenSearch** — Apache-2.0 fork with ES-comparable capability, AWS-managed option lowers ops
  cost; the pragmatic choice when license concerns or AWS-native deployment matter.
- **Algolia** — fully managed, hosted, extremely fast typo-tolerant instant search with a polished
  merchandising/personalization layer; strong for teams wanting to skip infra ops, at higher
  per-record/per-query cost.
- **Typesense / Meilisearch** — single-binary, in-memory, near-zero-ops engines optimized for
  product search/autocomplete with predictable millisecond latency; practical ceiling around tens
  of GB per node — best for small-to-mid catalogs or as a fast user-facing layer paired with a
  heavier system for analytics.
- **Postgres full-text search** — adequate when already running Postgres, small-to-medium dataset,
  modest requirements. Using raw `LIKE`/`ILIKE` at any real scale is an anti-pattern, but Postgres's
  built-in `tsvector`/GIN index is legitimate before adopting a dedicated engine.
- A common 2026 pattern is **polyglot**: a fast dedicated engine (Typesense/Algolia) for
  user-facing search, plus Elasticsearch/OpenSearch for internal analytics and complex aggregations
  on the same data.

### B. Hybrid search (keyword + semantic)

Combine BM25 lexical results with vector/ANN semantic results, then merge with **Reciprocal Rank
Fusion (RRF)**: `Score(d) = Σ 1/(k + rank(r,d))`, typically k=60. RRF sidesteps normalizing
incompatible score scales (BM25 vs. cosine similarity) by fusing on rank position instead. This is
the default hybrid pattern in Elasticsearch, OpenSearch, Vespa, and Weaviate; a cross-encoder
reranker is often layered on top for the final top-N results.

### C. Recommendation approach

- **Collaborative filtering (CF)** — learns from user-item interaction patterns (matrix
  factorization, implicit ALS); strong once sufficient interaction data exists, fails on cold start.
- **Content-based filtering** — matches item features/embeddings to user profile/history; works for
  new items, partially mitigates cold start, tends toward filter-bubble narrowness.
- **Hybrid** — blends CF + content-based + popularity fallback, the dominant real-world pattern.
- **Learned ranking models** (learning-to-rank / two-tower / deep retrieval+ranking) — a retrieval
  stage (ANN over learned embeddings) narrows millions of items to hundreds, then a ranking model
  (GBDT or neural) reorders for the final feed — the architecture used by YouTube, TikTok, and most
  large-scale feeds. Worth investing in only after basic relevance/CF is solid; expensive to build
  and maintain.

### D. Real-time personalization vs. batch-precomputed recommendations

Batch/precomputed (nightly or hourly jobs writing "for you" lists to a cache) is simple, cheap, and
sufficient for most mid-size products. Real-time (session-based re-ranking, streaming feature
updates) requires a feature store, streaming infra, and low-latency model serving — justified mainly
at large scale (large feeds, news, marketplaces) where freshness materially moves engagement.

## Anti-patterns

- **Using Postgres `LIKE`/`ILIKE` (or even naive `tsvector` without tuning) as "search" at real
  scale** — no typo tolerance, poor relevance ranking, full-table scans degrade badly past tens of
  thousands of rows.
- **Ignoring cold start** — shipping collaborative filtering without a popularity/content-based
  fallback leaves new users seeing empty/generic feeds and new items permanently invisible.
- **Over-investing in ML ranking before basic relevance is solid** — a well-tuned BM25/facet setup
  routinely outperforms a poorly-fed ML model.
- Skipping click/conversion logging early (no data to train ranking later), full reindexing instead
  of incremental/near-real-time updates causing stale results, treating semantic search as a
  drop-in replacement for keyword search rather than a complement (losing exact-match precision for
  SKUs/brand names).

## Reference implementations

- **Algolia** — managed hosted search with merchandising and semantic/agentic search layers, widely
  used in e-commerce.
- **Elastic (Elasticsearch)** — the default deep-relevance/analytics engine.
- **OpenSearch (AWS)** — Apache-licensed fork for AWS-native shops.
- **Typesense / Meilisearch** — open-source, single-binary engines for instant/product search.
- **YouTube / TikTok** — commonly cited public examples of retrieval-then-rank at massive scale.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `searchRecommendation` signal — a dedicated trade-off card
choosing between Postgres full-text/Typesense (small scale) and Elasticsearch/OpenSearch/Algolia
(larger scale), with cold-start-aware collaborative-filtering guidance for the recommendation half.

## Sources

- [Elasticsearch vs OpenSearch vs Typesense: Search Infrastructure Compared for 2026](https://www.askantech.com/elasticsearch-opensearch-typesense-search-infrastructure-comparison-2026/)
- [Postgres Full Text Search vs the rest — Supabase](https://supabase.com/blog/postgres-full-text-search-vs-the-rest)
- [Postgres vs ElasticSearch vs Algolia — Lantern Blog](https://lantern.dev/blog/search)
- [Advanced RAG — Understanding Reciprocal Rank Fusion in Hybrid Search — Guillaume Laforge](https://glaforge.dev/posts/2026/02/10/advanced-rag-understanding-reciprocal-rank-fusion-in-hybrid-search/)
- [Hybrid Search: BM25, Vector & Reranking Reference 2026 — Digital Applied](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026)
- [3 Modern Approaches to Solving Cold Start in RecSys (2026) — mlwhiz](https://www.mlwhiz.com/p/cold-start-problem-recsys-modern-approaches)
- [The Architecture of Recommendation Systems: From Collaborative Filtering to Deep Learning](https://developersvoice.com/blog/architecture/architecture-of-recommendation-systems/)
- [Ecommerce search solutions in 2025/2026 — Algolia](https://www.algolia.com/blog/ecommerce/ecommerce-search-solutions)
