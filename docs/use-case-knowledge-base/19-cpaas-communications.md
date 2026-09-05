# Communications & CPaaS — channel, sender, verification, and the regulation that gates them

**Status:** target design — none of the decision points below are reasoned about by `index.html`'s
rule engine today. The one adjacent behaviour that exists is a multi-channel routing note under
air-gapped/on-prem conditions, which names WhatsApp and voice as channels but makes no channel,
sender, verification or compliance recommendation.

---

## Business context

Communications is the first domain in this corpus that is gated by something other than engineering
judgement. In most domains a wrong pick is expensive; here a wrong pick means **no traffic at all**,
enforced at the carrier network, invisible to application logs. An architect who picks the right
database and the wrong sender type ships nothing.

It is also the first domain that *depends on* the others rather than sitting beside them. The
conversational layer reuses LLM-strategy reasoning for model choice, database reasoning for
conversation memory and vector storage, and IAM reasoning for silent network auth and passkeys.

The market read as of 2026: connectivity itself is commoditising — the Gartner CPaaS Magic Quadrant
places Twilio, Infobip, Sinch, Vonage and Proximus Global as Leaders on a $14.88B (2025) → ~$17.03B
(2026) market — and differentiation has moved up-stack to AI orchestration, data/CDP integration and
fraud control. AI capability is now a mandatory evaluation criterion rather than a bonus.

## Signals / triggers

OTP, one-time passcode, 2FA, two-factor, verification API, send code, check code, phone
verification, SMS, MMS, RCS, WhatsApp Business, WABA, WhatsApp template, A2P, P2A, short code, long
code, toll-free number, alphanumeric sender ID, sender ID, SMPP, SMSC, DLR, delivery receipt, status
callback, CPaaS, Twilio, Infobip, Sinch, Vonage, Bandwidth, Telnyx, MessageBird, aggregator, carrier
interconnect, direct-to-carrier, route quality, least-cost routing, DLT registration, TRAI, TCCCPR,
principal entity, header registration, template registration, transactional SMS, promotional SMS,
10DLC, TCR, brand registration, campaign registration, toll-free verification, STIR/SHAKEN, TCPA,
quiet hours, DND scrubbing, SMS pumping, AIT, artificially inflated traffic, toll fraud, SIM swap,
silent network authentication, number verification, GSMA Open Gateway, CAMARA, TS.43, IVR, voice
agent, ConversationRelay, conversational messaging, omnichannel, notification service, transactional
messaging, delivery rate, throughput limit, messages per second

## Decision points

### A. Is a technology recommendation the useful answer at all?

For a meaningful share of communications requests it is not, and saying so is the answer. Three
shapes where the stack is the least interesting part of the problem:

- **Regulated market entry.** The blocking path is registration lead time, not engineering. The
  correct output states the gating registrations and their sequence, then notes the stack is
  unremarkable.
- **Building a CPaaS rather than consuming one.** Carrier or aggregator interconnect agreements as a
  new entrant, wholesale-to-retail margin management, telecom licensing standing, and fraud
  liability for pumped traffic you owe the carrier for regardless of whether your customer pays —
  these gate the business. Naming Java, Kafka and Postgres is true and nearly useless.
- **Vendor lock-in migration.** The work is sender re-registration, template re-approval and
  number portability, not application code.

Recommend the stack *after* stating the binding constraint, never instead of it.

### B. Channel selection

| Channel | Use when | Cost/risk note |
|---|---|---|
| SMS | Universal floor; reach where nothing else is guaranteed | Highest fraud surface; per-message cost varies 3–10x by destination |
| RCS | Branded, rich replacement for SMS where the handset supports it | SMS fallback stays mandatory in the design, not optional |
| WhatsApp | Conversational and utility messaging with an existing user relationship | Per-message pricing since 1 July 2025; priced on the *recipient's* country |
| Voice | Accessibility, low SMS deliverability, high-value confirmation | Toll-fraud exposure |
| Email | Long-form, receipts, low urgency | Weak for time-boxed codes |
| Push / in-app | You already have the app installed | No carrier cost, no carrier reach |

WhatsApp's four template categories — Marketing, Utility, Authentication, Service — bill
differently. Service messages are free; Utility templates inside an open 24-hour customer-service
window are free; click-to-WhatsApp entries open a 72-hour free window. **Authentication templates
get no free-window relief**, which is precisely the category an OTP product lives in.

### C. Sender and number strategy

Each sender type carries its own compliance programme, so this choice is made *before* build, not
after. Long code, toll-free, short code, alphanumeric sender ID, WhatsApp Business Account and RCS
agent are six different registration paths, not six configuration values. Changing sender type
after launch means redoing registration, not editing config.

Throughput follows sender type and caps the application regardless of how the backend scales:
long code ~1 SMS/s, toll-free ~3 SMS/s, short code 10–100 SMS/s, with pooled senders summing.

### D. The verification ladder

| Level | Pattern | Right answer when |
|---|---|---|
| L1 | Managed OTP API — code generation, delivery, expiry, rate limiting, replay protection built in | The default. Hand-rolling OTP logic is almost always wrong |
| L2 | Multi-channel with fallback: SMS → voice → WhatsApp → email | Poor SMS delivery markets; accessibility requirements |
| L3 | Risk-adaptive — number intelligence (line type, carrier), SIM-swap check, then channel choice | Financial, PII or KYC-regulated flows |
| L4 | Push approve, TOTP, passkeys | Your own app is installed, or enterprise/high-security; removes network dependency |
| L5 | Silent network authentication — SIM-session handshake via operator API | Highest-conversion path where coverage exists |

Channel priority when free to choose: **Push → SMS → WhatsApp → Voice → Email.**

Silent auth is a *first-attempt optimisation with mandatory SMS fallback*, not a replacement. It
requires active cellular data, so real-world coverage is roughly 50% of users depending on region
and Wi-Fi-only users fail outright. Architect it as a cascade and instrument the fallback rate —
that number is the actual return. It also enables pay-per-success billing rather than
pay-per-message-sent, which removes the incentive structure behind artificially inflated traffic.
GSMA Open Gateway / CAMARA is the aggregation layer that makes it consumable without per-operator
integration; TS.43 is the network-agnostic path. Published conversion metrics do not exist — treat
vendor conversion claims as unverified.

### E. Regulatory preconditions — the failure is invisible to your logs

In several markets compliance is a precondition for any traffic, enforced at the network. A
non-compliant message is dropped silently: no error, no bounce, nothing in application logs.

**India (TCCCPR 2018, amended February 2025)** — the strictest common case:

| Control | Rule |
|---|---|
| DLT registration | Principal Entity registered on an operator DLT platform with KYC; biometric authentication required for new PE/telemarketer registrations since Feb 2025 |
| Headers | 6-character alphanumeric, with an operator-appended category suffix — `-T` transactional, `-S` service, `-P` promotional, `-G` government (from May 2025) |
| Templates | Every message variant pre-registered; variables typed (OTP, amount, name, date) since Oct 2024; unmatched messages dropped at network level |
| URLs | All CTAs pre-whitelisted on DLT; no public URL shorteners |
| Timing | Transactional/service/government 24/7; promotional restricted to 10:00–21:00 IST and dropped rather than queued outside it |
| OTP specifics | Must be `-T`, brand name in template, variable typed as OTP, no promotional content mixed in; RBI prohibits clickable links in banking OTPs; delivery within 30 minutes of a customer-initiated transaction |
| Penalties | Warning → 20 msg/day cap for 6 months → telecom resource disconnection. DPDP Act 2023 adds up to ₹250 crore for breaches |

**United States** — A2P 10DLC brand and campaign registration via TCR, toll-free verification, and
STIR/SHAKEN attestation for voice. **EU** — GDPR consent and erasure. **Global** — TCPA quiet hours
and DNC lists, PCI DSS where payment details are captured or recorded, HIPAA BAA where PHI is
carried.

The scheduling consequence is the one architects miss: registration lead time is measured in weeks
and runs in parallel with nothing. A timeline is at risk from registration, not from engineering.

### F. Fraud — AIT has moved past pattern matching

Attacker behaviour as of Q1 2026 has invalidated the older detection assumptions:

- Automation now **completes the whole verification workflow, including entering the OTP**, so
  "the code was consumed" is no longer evidence of a real user.
- Targets are randomised across carriers, regions and number families rather than sequential ranges.
- Geography has shifted toward EU markets previously treated as low risk, chosen for stringent
  regulation and low termination rates.
- AIT has spread beyond 2FA into app-download links, surveys and promo-code generation.
- Template-based phishing roughly doubled quarter on quarter.

Layered controls that still work: SMS pumping protection at the messaging layer, fraud analytics at
the verification layer, per-identity and per-IP rate limits, geo-permissions that hard-block
countries outside your business scope, and number intelligence before send. The economic controls
are the newer ones — velocity per destination *prefix*, conversion-rate anomaly per operator, and
cost-per-successful-verification as a live alarm rather than a monthly invoice surprise.

### G. Reliability primitives — what separates an integration from a production one

| Pattern | Specification |
|---|---|
| Backoff | On 429: exponential from 100ms, ×2, ±10% jitter, cap 30s, ~5 retries. Non-429 errors are investigated, not retried |
| Throughput budgeting | Rate-limit to what the sender pool supports, not to what you want |
| Idempotency | Client-supplied idempotency key per send; a retry after timeout must not double-charge or double-deliver |
| Thin receiver | Webhook handler validates the signature, enqueues, returns 200 immediately — 50 concurrent calls × 6 status events ≈ 300 invocations/sec |
| Signature validation | HMAC over URL + body; use the vendor SDK validator, never hand-rolled (parameter and port edge cases) |
| Status model | `queued → sent → delivered \| undelivered \| failed`; with a messaging service, `accepted` precedes `queued` |
| Fallback chains | Channel-level (SMS→voice) and vendor-level (primary→secondary), switched on measured delivery rate rather than on an outage page |
| Cost attribution | Tag tenant + campaign + channel + destination country at write time; retrofitting this is painful |

Delivery receipts are advisory in many markets — carriers misreport. Treat a DLR as a signal, not as
truth, and reconcile it against real conversion (was the code actually entered?) where the flow
allows.

### H. Buy versus build the transport layer

Building below the API means building an SMSC: SMPP gateway with persistent TX/RX/TRX binds per
client and per carrier (bind limits and window size cap throughput before application code does), a
store-and-forward queue with priority lanes so OTP never queues behind a marketing blast, a routing
engine selecting dynamically on delivery rate/latency/cost rather than a static least-cost-routing
table, a DLR state machine, a signed and retried webhook fabric, and active-active clustering that
fails over without losing in-flight messages.

This is a viable business and a poor default. The gating items are commercial — interconnect
agreements, route economics, licensing standing, fraud liability — not architectural.

### I. The agentic layer

| Capability | Architectural note |
|---|---|
| Real-time voice relay | WebSocket bridge ASR → LLM → TTS over a live call. The latency budget *is* the design; streaming responses are mandatory and barge-in handling is where most implementations fail |
| Conversation orchestration | Rules capturing SMS/voice/WhatsApp/RCS/web-chat into one conversation object with grouping and timeouts, replacing hand-rolled cross-channel thread stitching |
| Conversation memory | Durable profiles, traits, observations, summaries and semantic recall — a vector-store plus profile-store decision |
| Knowledge grounding | Retrieval over approved content at turn time; the same embedding/chunking/store decision as any other RAG system |
| Conversation intelligence | Language operators over transcripts for sentiment, script adherence, escalation and QA. Post-call batch versus real-time agent-assist is a distinct cost and latency choice |
| Human routing | Skills-based task routing, reservations, warm and cold transfer, barge and whisper. AI escalation is a routing problem, not a prompting problem |

## Anti-patterns

- **"We'll add compliance later."** In DLT and 10DLC markets there is no traffic to iterate on until
  registration completes. Later means never launching.
- **Rolling your own OTP generation, expiry and rate limiting** because the send is "just an API
  call." The send is the easy part; replay protection, per-identity throttling and fraud analytics
  are the product.
- **Treating a delivery receipt as proof of delivery.** Carriers misreport in many markets. If the
  question is "did the user get it," the answer lives in conversion, not in the DLR.
- **Processing webhooks inline.** Status callbacks arrive at multiples of your send rate; an inline
  handler turns a successful campaign into an outage.
- **One sender pool for OTP and marketing.** A marketing blast ahead of an OTP in the same queue is
  a failed login for a real user.
- **Blocking on `scope_verdict` grounds only in a caveat.** When regulation or commercial standing
  gates the project, burying that under a stack recommendation inverts the priority the reader needs.
- **Assuming silent auth replaces SMS.** Roughly half of users are not on cellular data at the
  moment of verification; without a fallback cascade those users cannot sign in at all.
- **Retrying non-429 errors.** A 400-class failure repeated five times is five charges and zero
  deliveries.

## Revisit triggers

- **§B (channel selection):** revisit when destination mix shifts materially by country — WhatsApp
  and SMS pricing key off the recipient's country, so a channel that was cheapest at launch can
  invert after geographic expansion.
- **§C (sender strategy):** revisit the moment sustained throughput approaches the sender type's
  ceiling, or when a second traffic class (marketing alongside transactional) appears — both mean a
  new registration path, not a configuration change.
- **§D (verification ladder):** revisit when the measured silent-auth fallback rate stops improving,
  or when fraud losses exceed the cost of moving to risk-adaptive L3.
- **§E (regulatory):** revisit on every new market, and whenever a regulator amends category or
  template rules — the Feb 2025 India amendments changed header suffixes and biometric requirements
  for entities already registered.
- **§H (buy vs build):** revisit only when aggregate message volume makes wholesale margin exceed
  the fully-loaded cost of interconnects, licensing and fraud liability.

## As implemented in `index.html`

**Not yet implemented.** No decision point in this document is reasoned about by the rule engine.
`detectSignals()` has no OTP, verification, sender-type, CPaaS-vendor or telecom-compliance signal,
and no `pickX()` function produces a communications recommendation.

The single adjacent behaviour is a channel-routing note emitted under air-gapped/on-prem conditions,
which observes that WhatsApp Business API and public voice carriers require internet reachability.
That is a network-boundary observation, not a communications recommendation, and it does not cover
channel selection, sender strategy, the verification ladder, regulatory preconditions or fraud.

Wiring any of this in means adding signal keywords from the Signals section above to both engines in
the same commit, per the repository's two-engines-one-behaviour rule.

## Sources

- [Gartner Magic Quadrant for CPaaS 2026: The Rundown — CX Today](https://www.cxtoday.com/service-management-connectivity/gartner-magic-quadrant-cpaas-2026/)
- [March 2026 Fraud Update: AIT Tactics, Weaponized Trust — Twilio](https://www.twilio.com/en-us/blog/insights/best-practices/quarterly-fraud-update-march-2026)
- [The Promise of Phone Number Silent Authentication APIs (white paper, Feb 2026) — Meta Engineering](https://engineering.fb.com/wp-content/uploads/2026/02/Meta-White-Paper-The-Promise-of-Silent-Auth-APIs.pdf)
- [India SMS Regulations, DLT Registration & TRAI Compliance Guide 2026 — Message Central](https://www.messagecentral.com/sms-guideline/india)
- [WhatsApp Business per-message pricing 2026 — Blueticks](https://blueticks.co/blog/whatsapp-business-pricing-change-2026-per-message)
- [The Complete Guide to SMSC Architecture for Modern CPaaS Platforms — Yelo Connect](https://yeloconnect.com/the-complete-guide-to-smsc-architecture-for-modern-cpaas-platforms/)
- [GSMA Open Gateway — Unlocking the Power of Network APIs](https://www.gsma.com/solutions-and-impact/gsma-open-gateway/open-gateway-unlocking-the-power-of-network-apis/)
- [Introducing the Twilio MCP Server and Skills — Twilio](https://www.twilio.com/en-us/blog/developers/introducing-twilio-mcp-skills)
- [Infobip AgentOS](https://www.infobip.com/agentos)
- [CPaaS X: Multi-tenant communication layer — Infobip Docs](https://www.infobip.com/docs/cpaas-x)

**Unsourced in this document:** the throughput figures in §C and the backoff parameters in §G are
conventional operating values cross-checked against the `twilio-developer-kit` skill pack rather
than against a primary carrier specification, and vary by vendor and destination — treat them as
starting points to verify per route, not as guarantees.
