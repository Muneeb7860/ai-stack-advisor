# Two-Sided Marketplace

**Status:** implemented — wired into `pickTradeoffs()` via the `marketplace` signal.

**Domain:** Platforms matching buyers/sellers or supply/demand with payments flowing between them —
Airbnb/Uber/Etsy-style products. Research date: August 2026.

## Business context

Relevant for any product where the platform's core value is matching two distinct user populations
(not serving one population against the platform's own inventory) and money changes hands between
them, with the platform taking a commission.

## Signals / triggers

`marketplace`, `two-sided platform`, `buyers and sellers`, `supply and demand`, `booking platform`,
`gig platform`, `on-demand platform`, `commission`, `take rate`, `escrow`, `split payment`,
`payout`, `seller onboarding`, `KYC`, `host/guest`, `driver/rider`, `listing`, `matching engine`,
`reviews and ratings`, `reputation system`, `trust and safety`, `fraud detection`, `Stripe Connect`,
`multi-vendor`.

## Decision points

### A. Matching / search architecture

Simple filtered SQL queries (Postgres + indexes/PostGIS) are fine at low scale (<10K listings) but
degrade fast with facets, relevance ranking, and free text. A dedicated search index —
Elasticsearch/OpenSearch (self-hosted/managed, full control) vs. Algolia (fully managed SaaS,
faster time-to-market, typo-tolerant, higher cost at scale) — becomes worth it once listing volume
and relevance needs grow. Geo-matching: PostGIS/geohash indexing for radius queries, or specialized
geo-dispatch (Uber's open-sourced H3 hexagonal grid) for real-time driver-rider matching at massive
throughput. Most teams either over-invest in Elasticsearch before they have the listing volume to
need it, or under-invest and hit a wall at scale — match the tool to actual current volume, not
aspirational volume.

### B. Payments architecture

Rolling your own ledger + direct bank payouts requires becoming (or partnering with) a licensed
money transmitter, and building KYC/AML, 1099-K tax reporting, dispute/chargeback handling, and PCI
compliance from scratch — widely cited as one of the most expensive, risky mistakes marketplace
founders make. **Stripe Connect** is purpose-built for this: seller onboarding/KYC, split payments
(`application_fee_amount`), delayed payouts (functional escrow via payout timing), 1099-K
generation, and fraud screening (Radar). Alternatives: **Adyen for Platforms**, **Braintree/PayPal
marketplace**, **Mangopay** (EU-focused, true held-funds escrow wallets rather than delayed
transfer) — chosen when geography, currency mix, or a genuine escrow-wallet requirement is a hard
constraint. Consensus 2026 guidance: use a marketplace payments platform rather than building
payment splitting/escrow in-house.

### C. Trust & safety pipeline

Reactive-only (reviews + manual support tickets) is cheapest to launch but scams/abuse scale faster
than support teams once GMV grows. A layered pipeline — identity verification/KYC at onboarding
(Stripe Identity, Persona, Onfido) → real-time transaction risk scoring (rules engine or ML fraud
model — Sift, Unit21, Stripe Radar) → reputation system (weighted, recency-decayed review scores,
verified-review gating) → post-hoc dispute/chargeback resolution workflow — should be built early
rather than retrofitted after a fraud incident or trust erosion forces a scramble.

### D. Supply-side vs. demand-side app architecture

A single shared app/monolith with role-based views has the least engineering overhead initially, but
sellers need dashboards/analytics/inventory tools while buyers need discovery/checkout flows — UX
compromises pile up and release coupling slows both teams down. Separate frontend apps (supply app +
demand app) behind a shared core API, often with a BFF layer per app, lets each team iterate
independently — mirrors patterns at Airbnb (host vs. guest) and Uber (driver vs. rider). Trade-off:
more infrastructure, duplicated auth/session logic, coordination overhead to keep the shared domain
model consistent.

## Anti-patterns

- **Building custom payment splitting, wallets, or escrow logic** instead of adopting Stripe Connect
  (or Adyen for Platforms/Mangopay) — underestimates KYC, tax, licensing, and chargeback complexity.
- **Deferring trust & safety** until after a fraud incident or PR crisis forces a scramble.
- **Serving both buyer and seller experiences from one monolithic app/UI** — forces UX compromises
  on both sides and creates deployment coupling between fundamentally different roadmaps.
- **Reaching for Elasticsearch/Algolia and complex geo-matching before there's enough listing volume
  to justify it** (or the reverse — staying on raw SQL filters long past the point relevance/facets
  matter).
- **Treating reviews/ratings as static rather than recency-weighted and fraud-resistant** (fake
  review farming).

## Reference implementations

- **Stripe Connect** — the dominant marketplace payments/split-payment platform.
- **Adyen for Platforms**, **Mangopay** — enterprise/EU alternatives.
- **Sharetribe** — marketplace-platform-as-a-service whose public engineering content documents
  common marketplace payment/architecture patterns.
- **Airbnb and Uber engineering blogs** — documented evolution from monolith to service-oriented
  architecture, separate host/guest and driver/rider experiences; Uber's H3 geospatial indexing for
  driver-rider matching.

## Revisit triggers

- **§A (search):** simple filtered SQL is fine under roughly **10K listings** — once volume and
  relevance needs (facets, free text, ranking) grow past that, a dedicated search index earns its
  cost. Match the tool to actual current volume, not aspirational volume, in either direction.
- **§C (trust & safety):** a reactive-only pipeline (reviews + manual tickets) is the cheapest way
  to launch, but revisit before a fraud incident or trust erosion forces the scramble — GMV growth
  outpacing support-team capacity to catch scams manually is the signal, not a fixed calendar date.
- **§D (supply/demand app split):** if UX compromises from a shared app (seller dashboards vs. buyer
  discovery flows fighting for the same screens) are visibly slowing either team's iteration speed,
  that is the trigger to split into separate supply-side/demand-side apps behind a shared core API —
  not a default starting architecture.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `marketplace` signal — a dedicated trade-off card
recommending Stripe Connect (or Adyen/Mangopay by geography/escrow need) over building payment
splitting in-house.

## Sources

- [Stripe – Two-Sided Marketplace Strategy: How to Build and Scale](https://stripe.com/resources/more/two-sided-marketplace-strategy)
- [No7 Software – Stripe Connect: Engineering Marketplace Payments (2026)](https://no7software.co.uk/blog/stripe-connect-marketplace-payments-engineering)
- [Sharetribe – Marketplace Payments: The Complete Guide](https://www.sharetribe.com/academy/marketplace-payments/)
- [Low Code Agency – Escrow and Split Payment Systems in Marketplaces](https://www.lowcode.agency/blog/escrow-split-payment-systems-in-marketplaces)
- [Netguru – Bloomreach vs Algolia vs Elasticsearch: Search Engines for Ecommerce in 2026](https://www.netguru.com/blog/bloomreach-vs-algolia-vs-elasticsearch)
- [Unit21 – Marketplace Risk: Common Scams & How to Prevent Marketplace Fraud](https://www.unit21.ai/trust-safety-dictionary/marketplace-risk)
- [TechVinta – Marketplace Trust & Safety Playbook: 6 Pillars (2026)](https://techvinta.com/blog/marketplace-trust-and-safety-playbook)
- [ByteByteGo – A Brief History of Airbnb's Architecture](https://blog.bytebytego.com/p/a-brief-history-of-airbnbs-architecture)
- [DreamFactory – 4 Microservices Examples: Amazon, Netflix, Uber, and Etsy](https://blog.dreamfactory.com/microservices-examples)
