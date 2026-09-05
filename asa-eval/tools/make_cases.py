"""Writes the starter case corpus. Run once; then edit the YAML by hand.

Every golden below is status: DRAFT. Draft cases are executed and reported but
excluded from the headline score until a human architect reviews them and flips
the status to REVIEWED. That gate is the whole point -- a benchmark whose answers
were written by a model is a benchmark that measures agreement with a model.
"""

from pathlib import Path

CASES: dict[str, str] = {}

CASES["t01-multitenant-oltp"] = """
id: t01-multitenant-oltp
title: B2B SaaS multi-tenant OLTP store
tags: [technology, database, saas]
input:
  mode: prd
  text: |
    We are building a B2B workflow SaaS. Expected 400 tenants in year one, largest
    tenant ~2M rows in the busiest table, most under 50k. Tenants are contractually
    promised logical data isolation and the ability to export or delete all their
    data on request. Team is 6 engineers, strong Java/Spring, no dedicated DBA.
    Reads are heavily filtered by tenant. We need per-tenant point-in-time restore.
golden:
  status: DRAFT
  binding_constraint: technology
  scope_verdict: full
  required_flags: [tenant_isolation, point_in_time_restore]
  forbidden: []
  domains:
    database:
      acceptable: [postgresql, postgres, mysql]
      preferred: postgresql
      unacceptable: [mongodb, dynamodb, cassandra]
      required_because: "Relational with row-level security and mature PITR tooling."
  should_rule_out: [database-per-tenant]
  reasoning_rubric: |
    Should engage with the isolation-vs-operability trade-off: shared schema with
    row-level security is operable by a team with no DBA, database-per-tenant gives
    the cleanest deletion and restore story but 400 databases is an ops burden that
    this team cannot carry. Should note per-tenant PITR is the constraint that most
    strongly argues against a single shared table, and should flag that the choice
    is expensive to reverse once tenant data exists.
"""

CASES["t02-rag-internal-docs"] = """
id: t02-rag-internal-docs
title: Retrieval layer for internal document assistant
tags: [technology, llm_strategy, rag]
input:
  mode: prd
  text: |
    Internal assistant over ~120k policy and process documents, mostly PDF and
    Confluence exports. Around 300 employees will query it. Answers must cite the
    source document. Documents change weekly. Latency target under 3 seconds.
    We already run Postgres. No GPU budget for now; we have an existing agreement
    with a hosted model provider.
golden:
  status: DRAFT
  binding_constraint: technology
  scope_verdict: full
  required_flags: [citation, reindex]
  forbidden: [fine_tuning]
  domains:
    llm_strategy:
      acceptable: [rag, retrieval augmented generation, hosted model with rag]
      preferred: rag
      unacceptable: [fine-tuning, continued pretraining]
      required_because: "Weekly-changing corpus and citation requirement rule out weight-baked knowledge."
  should_rule_out: [fine-tuning]
  reasoning_rubric: |
    Should identify that weekly document churn plus a hard citation requirement makes
    retrieval mandatory and fine-tuning actively wrong. Should address chunking and
    reindexing cadence, and should note pgvector is a defensible choice given Postgres
    is already operated, versus a dedicated vector store which adds a component to run.
    Should mention that 120k documents is small enough that the vector store choice is
    cheap to reverse.
"""

CASES["t03-event-ingestion"] = """
id: t03-event-ingestion
title: Event ingestion for device telemetry
tags: [technology, backend, scale]
input:
  mode: prd
  text: |
    IoT telemetry from 50,000 devices reporting every 30 seconds. Roughly 1,700
    events/sec steady, 5x burst on the hour when devices sync. Events must not be
    lost. Consumers: a real-time alerting service and a nightly analytics batch.
    We run on AWS. Team of 8, comfortable with Java, no Kafka experience.
golden:
  status: DRAFT
  binding_constraint: technology
  scope_verdict: full
  required_flags: [durability, replay, burst]
  forbidden: []
  domains:
    backend:
      acceptable: [kafka, msk, kinesis, amazon kinesis]
      preferred: kinesis
      unacceptable: [rabbitmq, sqs standard queue]
      required_because: "Two independent consumers with different cadences need replayable log semantics, not a queue."
  should_rule_out: [sqs]
  reasoning_rubric: |
    Should recognise that two consumers with different read patterns (real-time and
    nightly batch) need a replayable log rather than a queue, which eliminates plain
    SQS. Should weigh Kafka's power against a team with no Kafka experience and no
    platform team, and should be explicit that the operational cost of self-managed
    Kafka is the deciding factor rather than throughput, since 1,700/sec is modest
    for any of these options.
"""

CASES["t04-analytics-store"] = """
id: t04-analytics-store
title: Analytics store for product usage reporting
tags: [technology, database, analytics]
input:
  mode: prd
  text: |
    We need customer-facing usage dashboards. Around 2TB of event data growing 200GB
    a month, queries are aggregations over time ranges grouped by a handful of
    dimensions. Dashboards must load in under 2 seconds for the last 90 days.
    Data can be up to 15 minutes stale. Small data team, currently everything is in
    Postgres and the dashboard queries are timing out.
golden:
  status: DRAFT
  binding_constraint: technology
  scope_verdict: full
  required_flags: [columnar, freshness]
  forbidden: []
  domains:
    database:
      acceptable: [clickhouse, duckdb, snowflake, bigquery, timescaledb]
      preferred: clickhouse
      unacceptable: [mongodb, elasticsearch]
      required_because: "Time-bucketed aggregation over a fixed dimension set is a columnar workload."
  should_rule_out: [postgres]
  reasoning_rubric: |
    Should identify this as a columnar OLAP workload and explain why row-store
    Postgres is timing out rather than just asserting a replacement. Should treat the
    15-minute staleness allowance as the thing that makes a separate analytical store
    viable. Should weigh a managed warehouse against a self-hosted engine given a
    small data team, and note that customer-facing latency targets are a stricter
    requirement than internal BI.
"""

CASES["t05-internal-admin-ui"] = """
id: t05-internal-admin-ui
title: Internal admin UI for operations team
tags: [technology, frontend, reversibility]
input:
  mode: prd
  text: |
    Internal CRUD admin panel for our 12-person ops team. About 30 screens over
    existing REST APIs. No public exposure, no SEO, no mobile requirement. We want
    it in about six weeks. Two backend engineers will build it; neither is a
    specialist frontend developer.
golden:
  status: DRAFT
  binding_constraint: technology
  scope_verdict: full
  required_flags: [low_reversal_cost]
  forbidden: []
  domains:
    frontend:
      acceptable: [react, vue, svelte, htmx, retool, admin framework, refine, next.js]
      preferred: react
      unacceptable: []
      required_because: "Any mainstream choice works; the honest answer is that this decision barely matters."
  should_rule_out: []
  reasoning_rubric: |
    A good answer says plainly that this is a low-stakes, cheaply reversible decision
    and that arguing about the framework is a poor use of the team's time. It should
    weight developer familiarity and time-to-ship above technical merit, and should
    seriously consider an off-the-shelf admin tool given two non-specialist engineers
    and a six-week window. Confidence should be high but the stated impact low.
"""

CASES["r01-india-otp-verify"] = """
id: r01-india-otp-verify
title: OTP verification product for the India market
tags: [regulatory, communications, cpaas]
input:
  mode: prd
  text: |
    We are launching an OTP verification API for Indian businesses. MVP is send-code
    and check-code over SMS, with a REST API and a dashboard. Target customers are
    fintech and e-commerce companies. We plan to launch in eight weeks on AWS
    Mumbai with a Spring Boot backend.
golden:
  status: DRAFT
  binding_constraint: regulatory
  scope_verdict: partial
  required_flags: [dlt_registration, template_registration, transactional_category]
  forbidden: []
  domains:
    backend:
      acceptable: [java, spring, spring boot]
      preferred: spring boot
      unacceptable: []
  should_rule_out: []
  reasoning_rubric: |
    The stack here is unremarkable and the answer should say so. The binding
    constraint is Indian telecom regulation: DLT registration as a principal entity
    or telemarketer, header and content template pre-registration, OTP traffic having
    to be transactional category, and URL whitelisting. A good answer states that the
    eight-week timeline is at risk from registration lead times rather than from
    engineering, and that non-compliant messages are dropped silently at the network
    so nothing in application logs will explain the failure.
"""

CASES["r02-eu-health-residency"] = """
id: r02-eu-health-residency
title: Patient-facing scheduling platform for EU clinics
tags: [regulatory, cloud, health]
input:
  mode: prd
  text: |
    Appointment scheduling used by clinics in Germany and France. Stores patient
    names, contact details, appointment reasons and clinician notes. Clinics have
    told us data must not leave the EU and several have asked about processing
    agreements. We would like to use a US-managed AI service to summarise notes.
    Team wants to move fast on a serverless stack.
golden:
  status: DRAFT
  binding_constraint: regulatory
  scope_verdict: partial
  required_flags: [data_residency, processing_agreement, special_category_data]
  forbidden: []
  domains:
    cloud:
      acceptable: [eu region, aws eu, azure eu, gcp eu, ovh, scaleway, hetzner]
      preferred: eu region
      unacceptable: [us region]
      required_because: "Stated residency requirement forecloses US-region processing."
  should_rule_out: [us-hosted ai summarisation]
  reasoning_rubric: |
    Should treat clinician notes as special-category health data under GDPR rather
    than ordinary PII, and should identify residency as a hard gate that eliminates
    options rather than a preference to trade off. Should flag that a US-managed
    summarisation service is a transfer problem, not a latency or cost problem, and
    that the answer depends on contractual terms the advisor cannot verify. Should
    be explicit about what it cannot determine.
"""

CASES["r03-us-a2p-messaging"] = """
id: r03-us-a2p-messaging
title: US appointment reminders by SMS
tags: [regulatory, communications]
input:
  mode: prd
  text: |
    We want to send appointment reminders by SMS to US customers of our salon
    booking product. Roughly 40,000 messages a month across our merchant base,
    sent from a single number. Launching next month.
golden:
  status: DRAFT
  binding_constraint: regulatory
  scope_verdict: partial
  required_flags: [a2p_registration, consent, throughput]
  forbidden: []
  domains:
    communications:
      acceptable: [toll-free, short code, messaging service, sender pool, 10dlc]
      preferred: messaging service
      unacceptable: [single long code]
      required_because: "A single long code cannot carry 40k/month across multiple merchants at ~1 msg/sec."
  should_rule_out: [single long code]
  reasoning_rubric: |
    Should catch two independent problems: registration (A2P brand and campaign
    registration is required before traffic flows, and it takes time) and throughput
    (one long code at roughly one message per second cannot deliver the peaks implied
    by 40k a month). Should also raise consent capture as a legal requirement, and
    should note that sending on behalf of merchants makes this an ISV pattern with
    per-merchant registration rather than a single brand.
"""

CASES["c01-build-cpaas-carrier"] = """
id: c01-build-cpaas-carrier
title: Build a CPaaS down to the carrier
tags: [commercial, cpaas, wrong-question]
input:
  mode: prd
  text: |
    We want to build our own CPaaS. Not reselling -- we want to run our own SMSC,
    hold direct carrier interconnects, and sell an SMS and OTP API to enterprises.
    What stack should we build it on? We are a Java shop with 12 engineers.
golden:
  status: DRAFT
  binding_constraint: commercial
  scope_verdict: wrong_question
  required_flags: [carrier_interconnect, route_economics, licensing]
  forbidden: []
  domains: {}
  should_rule_out: []
  reasoning_rubric: |
    The correct response leads by saying a stack recommendation addresses a small
    fraction of this problem. The gating items are commercial and regulatory: getting
    carrier or aggregator interconnect agreements as a new entrant, managing route
    quality and the margin between wholesale and retail price, telecom licensing or
    registration standing, and carrying fraud liability for pumped traffic that you
    owe the carrier for regardless of whether your customer pays. Naming Java, Kafka
    and Postgres is true and nearly useless here. A good answer says that explicitly
    rather than burying it in a caveat.
"""

CASES["c02-locked-in-migration"] = """
id: c02-locked-in-migration
title: Replace an incumbent analytics vendor
tags: [commercial, migration]
input:
  mode: prd
  text: |
    Our analytics vendor is expensive and we want to move to something better. We
    are 14 months into a 3-year committed contract with a minimum annual spend, and
    our contract includes the data pipeline our finance reporting depends on.
    Engineering wants to move to an open-source stack this quarter.
golden:
  status: DRAFT
  binding_constraint: commercial
  scope_verdict: partial
  required_flags: [committed_spend, contract_term]
  forbidden: []
  domains: {}
  should_rule_out: []
  reasoning_rubric: |
    Should lead with the contract, not the technology: a committed minimum spend
    means migrating this quarter pays for two stacks simultaneously for the remaining
    20 months, so the sensible sequencing question is when to start rather than what
    to move to. Should identify finance reporting as the risk-bearing dependency and
    suggest running in parallel through at least one reporting cycle. Technology
    options are secondary and should be presented as such.
"""

CASES["o01-small-team-microservices"] = """
id: o01-small-team-microservices
title: Microservices platform for a two-engineer team
tags: [organizational, architecture]
input:
  mode: prd
  text: |
    We are two engineers building a marketplace MVP. We want to do it properly from
    the start: microservices on Kubernetes, service mesh, event-driven communication,
    separate databases per service, full observability stack. We expect to raise a
    seed round in nine months.
golden:
  status: DRAFT
  binding_constraint: organizational
  scope_verdict: wrong_question
  required_flags: [team_size, operational_burden]
  forbidden: [service mesh, kubernetes]
  domains:
    backend:
      acceptable: [monolith, modular monolith, majestic monolith]
      preferred: modular monolith
      unacceptable: [microservices, service mesh]
      required_because: "Two engineers cannot operate a distributed system and ship a marketplace in nine months."
  should_rule_out: [microservices]
  reasoning_rubric: |
    Should say directly that the constraint is team capacity, not technology, and
    that this architecture would consume the runway it is meant to protect. Should
    make the case for a modular monolith with clean internal boundaries as the path
    that preserves the option to split later. Should push back on 'properly from the
    start' as a premise rather than accommodating it. Being agreeable here is the
    failure mode.
"""

CASES["o02-realtime-no-oncall"] = """
id: o02-realtime-no-oncall
title: Real-time trading alerts with no on-call rotation
tags: [organizational, reliability]
input:
  mode: prd
  text: |
    We want to offer real-time price alerts to traders, delivered within one second
    of a market move, 24 hours a day on weekdays. We have four engineers, all in one
    timezone, and no on-call rotation. Leadership does not want to fund one.
golden:
  status: DRAFT
  binding_constraint: organizational
  scope_verdict: partial
  required_flags: [on_call, availability_target]
  forbidden: []
  domains: {}
  should_rule_out: []
  reasoning_rubric: |
    Should name the mismatch between a 24-hour latency-sensitive commitment and the
    absence of anyone to answer a page at 3am. Should present the honest options:
    fund a rotation, buy managed services that shift the operational burden, or lower
    the promise to something four people in one timezone can actually keep. Should
    not paper over the gap with a technology recommendation and should note that
    resilient architecture reduces but does not eliminate the need for a human.
"""

CASES["d01-classification-no-labels"] = """
id: d01-classification-no-labels
title: Document classification with no labelled data
tags: [data, ml, wrong-question]
input:
  mode: prd
  text: |
    We want to automatically classify incoming supplier documents into 40 categories
    with 95% accuracy. We have about 900,000 historical documents in blob storage.
    They have never been categorised. Which model should we train and what should we
    serve it on?
golden:
  status: DRAFT
  binding_constraint: data
  scope_verdict: wrong_question
  required_flags: [labelled_data, accuracy_target]
  forbidden: []
  domains: {}
  should_rule_out: []
  reasoning_rubric: |
    Should identify that 900k unlabelled documents is not a training set and that no
    model or serving choice is meaningful until labels exist. Should question the 95%
    figure across 40 categories as a target set without a measured baseline, and note
    that per-class accuracy in a 40-way problem is where such targets fail. Should
    propose an achievable first step -- an LLM zero-shot or few-shot baseline to
    bootstrap labels, human review of a stratified sample -- rather than a training
    architecture. Recommending a model here would be answering the wrong question.
"""

CASES["d02-corpus-rights"] = """
id: d02-corpus-rights
title: Assistant trained on aggregated customer content
tags: [data, llm_strategy, rights]
input:
  mode: prd
  text: |
    We host content for 2,000 customers and want to build an assistant that answers
    questions using patterns learned across all of them, so smaller customers benefit
    from what larger ones have written. Our terms of service say we may process
    customer data to provide the service. We want to start next quarter.
golden:
  status: DRAFT
  binding_constraint: data
  scope_verdict: partial
  required_flags: [data_rights, cross_tenant, tenant_isolation]
  forbidden: []
  domains:
    llm_strategy:
      acceptable: [per-tenant rag, tenant-scoped retrieval, opt-in]
      preferred: per-tenant rag
      unacceptable: [cross-tenant fine-tuning, pooled training]
      required_because: "Cross-tenant learning from customer content is a rights question before it is an architecture."
  should_rule_out: [cross-tenant fine-tuning]
  reasoning_rubric: |
    Should recognise that 'process to provide the service' very likely does not cover
    using one customer's content to benefit another, and that this is a legal
    determination the advisor cannot make. Should distinguish tenant-scoped retrieval
    (defensible) from pooled training (leaks across the tenant boundary and is hard
    to undo once weights exist). Should flag the irreversibility: you cannot remove
    one customer's contribution from a trained model on request.
"""

CASES["p01-vague-ai-platform"] = """
id: p01-vague-ai-platform
title: Underspecified AI platform request
tags: [product, underspecified]
input:
  mode: prd
  text: |
    We want to build an AI platform for our enterprise customers. It should use
    agents, be scalable and secure, integrate with everything, and give us a
    competitive advantage. Budget is flexible. What should we build it on?
golden:
  status: DRAFT
  binding_constraint: product
  scope_verdict: wrong_question
  required_flags: [underspecified, missing_requirements]
  forbidden: []
  domains: {}
  should_rule_out: []
  reasoning_rubric: |
    Should decline to produce a confident stack from this and say why: there is no
    stated user, workload, data, latency requirement, volume or success criterion, so
    any recommendation would be arbitrary and the confidence attached to it would be
    fictional. Should ask the small number of questions that would actually unblock a
    recommendation. Emitting a plausible-looking stack here is the single worst
    failure mode this product has, because the output looks identical to a
    well-grounded one.
"""


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "cases"
    out.mkdir(exist_ok=True)
    for name, body in CASES.items():
        (out / f"{name}.yaml").write_text(body.lstrip())
    print(f"wrote {len(CASES)} cases to {out}")


if __name__ == "__main__":
    main()
