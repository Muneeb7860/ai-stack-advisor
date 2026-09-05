# Industry verticals — the spine you integrate with and the shell you must satisfy

**Status:** partial — `detectSignals()` recognises five verticals (healthcare, finance, ecommerce,
retail, defense) and uses them for compliance hints only. Nothing in either engine knows what a
vertical's system of record is, what integration protocol it speaks, or which of the three
regulatory shapes applies. Those are the decision points below, and none of them is implemented.

---

## Business context

A stack recommendation for a vertical project is mostly a recommendation about **how to integrate
with the incumbent system of record, and what the regulator will let you ship**. Choosing Postgres
over MySQL matters far less than knowing that the hospital's EHR speaks HL7 v2 and FHIR, that the
integration goes through an interface engine, and that the customer's EHR team controls the
timeline.

This is the second domain that constrains the other domains rather than sitting beside them.
Vertical selects protocol; protocol constrains the integration architecture; the regulatory shell
caps deployment options before any technology is chosen.

There is no single count of "how many domains exist" — it depends who is counting. GICS has 11
sectors, NAICS has 20 (exhaustive by construction, so nothing in the economy is missing), and the
software-buyer lens recognises roughly 18 verticals that actually buy industry-specific software.
The three answer different questions: use NAICS for completeness, the buyer lens for advice.
Wholesale trade is a NAICS sector but barely a software vertical; life sciences is a large software
vertical buried inside NAICS "Manufacturing" and "Professional Services".

## Signals / triggers

patients, clinicians, providers, EHR, EMR, HL7, FHIR, DICOM, PACS, HIPAA, claims, payer,
policyholders, premiums, underwriting, claims adjuster, ACORD, actuarial, core banking, ledger,
settlement, ISO 20022, SWIFT, ISO 8583, open banking, AML, KYC, Basel, subscribers, MSISDN, BSS,
OSS, charging, interconnect, number portability, TM Forum, SKUs, storefront, basket, fulfilment,
order management, EDI, GS1, GTIN, guests, reservations, rooms, PMS, channel manager, rate parity,
OTA, GDS, shipments, consignments, waybill, TMS, WMS, ELD, customs, freight, telematics, work
orders, shop floor, MES, SCADA, PLC, historian, OPC-UA, ISA-95, OT network, substation, grid,
meter, AMI, DERMS, IEC 61850, NERC CIP, BIM, IFC, permitting, lease accounting, students,
enrolment, SIS, LMS, FERPA, LTI, sorties, mission systems, C4ISR, ITAR, CMMC, DO-178C,
classified enclave, tactical data link, growers, agronomy, ISOBUS, yield maps, rights window,
royalties, MAM, DAM, DRM, matters, ethical wall, LEDES, e-discovery, clinical trial, GxP,
21 CFR Part 11, CDISC, LIMS, case management, FedRAMP, StateRAMP, records retention

## Decision points

### A. Every stack has three layers, and only one of them is industry-specific

```
REGULATORY SHELL   what you must prove, to whom, before you may operate
VERTICAL SPINE     the system of record unique to this industry
HORIZONTAL CORE    the same in every industry on earth
```

The **horizontal core** — ERP, CRM, identity, data platform, observability, CI/CD, billing — is
identical everywhere. A retailer and a defence contractor buy the same categories and often the
same products. Every other document in this corpus is about this layer.

The **vertical spine** is the one application the business cannot operate without, which owns the
authoritative data and which everything else integrates around. It is almost never replaced;
replacement projects run for years and often fail. Any greenfield project in that vertical is, in
practice, a satellite of it.

The **regulatory shell** turns options into non-options. It decides what is legal before anyone
decides what is good.

### B. Identify the vertical from the vocabulary, not from a stated industry

Requirements rarely say "we are a healthcare company". They say "patients", "policyholders",
"subscribers", "guests", "shipments", "sorties", "growers", "matters". The noun for the customer is
the most reliable vertical signal in a requirement document, and it is present even when an
explicit industry statement is not.

### C. The spine is a precondition, not a recommendation

Emit it as something to confirm, not something to choose: *"You will be integrating with an EHR.
Confirm which one, and who owns that relationship."* Recommending a system of record is almost
always wrong — the customer already has one, and it predates the project.

| Vertical | System of record (the spine) |
|---|---|
| Banking | Core banking platform |
| Insurance | Policy administration system |
| Capital markets | OMS/EMS plus risk engine |
| Healthcare providers | EHR |
| Life sciences | LIMS + CTMS + regulatory vault |
| Telecommunications | BSS/OSS stack |
| Retail & e-commerce | Commerce platform + order management |
| Hospitality & travel | PMS (property management system) |
| Transport & logistics | TMS + WMS |
| Manufacturing | ERP + MES/MOM |
| Energy & utilities | SCADA/EMS/ADMS + customer information system |
| Construction & property | BIM + project controls / property management |
| Government | Case management + permitting/licensing |
| Defence & aerospace | Mission systems / C4ISR + PLM |
| Education | SIS (student information system) |
| Agriculture | FMIS (farm management information system) |
| Media | MAM/DAM + rights management |
| Legal & professional | Practice/matter management + DMS |

### D. The integration protocol is the highest-value single fact

Each vertical has a dominant data-exchange standard. Knowing it says more about a project's real
shape than any technology preference the customer states.

| Vertical | Dominant standard(s) | What it constrains |
|---|---|---|
| Healthcare | HL7 v2, FHIR R4/R5, DICOM, X12 (US claims) | Every integration; an interface engine is mandatory |
| Banking / payments | ISO 20022, SWIFT MT/MX, ISO 8583, Open Banking | Message formats, settlement windows, reconciliation |
| Insurance | ACORD | Policy, claims and broker exchange |
| Capital markets | FIX, FpML, ISO 20022 | Order flow, latency budgets, post-trade |
| Telecom | TM Forum ODA/Open APIs, 3GPP, Diameter, SMPP | Catalogue shape, charging, interconnect |
| Retail / e-commerce | EDI (X12/EDIFACT), GS1 (GTIN, EPCIS) | Supplier and logistics integration |
| Logistics | EDI X12 (204/214/990), EDIFACT, IATA, AIS | Carrier integration, customs |
| Travel / hospitality | HTNG, OpenTravel, IATA NDC, GDS | Distribution, rate and availability sync |
| Manufacturing | OPC-UA, MQTT Sparkplug, ISA-95, MTConnect | The OT/IT boundary, real-time constraints |
| Energy / utilities | IEC 61850, IEC CIM (61970/61968), DNP3, Modbus | Substation and grid interoperability |
| Construction | IFC/BIM, COBie, MISMO | Model exchange, handover |
| Government | NIEM, FedRAMP boundaries | Inter-agency data sharing |
| Defence | Link 16, DDS, FACE, STANAG, MIL-STD-1553 | Real-time messaging, certification |
| Education | LTI, SCORM/xAPI, Ed-Fi, OneRoster | Tool interoperability |
| Agriculture | ISOBUS (ISO 11783), ADAPT | Machine and agronomy data |
| Media | SMPTE, MXF, IMF, EIDR, CMAF/DASH/HLS | Asset exchange and delivery |
| Life sciences | CDISC (SDTM/ADaM), HL7, IDMP | Trial data, submissions |
| Legal | LEDES, EDRM | Billing exchange, disclosure |

### E. Regulation has three shapes, and they fail differently

This is the distinction that matters for a binding-constraint verdict, because two of the three are
schedule risks and the third is a design-time constraint:

- **Registration** gates you *before launch*. Telecom DLT and A2P 10DLC, FedRAMP authorisation,
  WhatsApp Business account approval. Lead time is measured in weeks or months and runs in parallel
  with nothing. A stated launch date is at risk from registration, not from engineering.
- **Certification** gates *each release*. DO-178C, GxP computer-system validation, medical-device
  submissions. It caps release cadence permanently, regardless of engineering practice — every
  deployment is a validated deployment.
- **Conduct** gates *behaviour continuously*. GDPR, HIPAA, TCPA, PCI DSS. This one is a design-time
  constraint on data flow, retention and consent rather than a date on a calendar.

A requirement naming a registration or certification regime should push the scope verdict toward
partial, with the timeline flagged. A conduct regime changes the architecture instead.

### F. The OT/IT boundary appears in four verticals and behaves identically in all of them

Manufacturing, energy, transportation and defence all have a line below which sit deterministic
real-time systems with twenty-year lifecycles that cannot be patched on your schedule, are often
air-gapped, and answer to safety certification rather than to a deployment pipeline. Cloud-first
thinking stops at that line. Recognising the pattern once transfers to all four.

### G. Data gravity predicts architecture better than the vertical's name

- **Large-object** problems: healthcare imaging, media assets, satellite and geospatial data.
- **High-transaction-rate** problems: banking, capital markets, telecom charging.
- **Intermittent-connectivity** problems: agriculture, logistics, field service — offline-first is
  mandatory rather than a nicety.

Two verticals with different names and the same data-gravity shape need more similar architectures
than two projects inside one vertical with different shapes.

### H. Defining constraints worth stating outright

| Vertical | The constraint that dominates |
|---|---|
| Banking | Ledger correctness; strict consistency beats availability |
| Insurance | 30-year product lifecycles; data models outlive the code |
| Healthcare | You integrate with the EHR; you do not replace it |
| Life sciences | Every change is a validated change; velocity is capped by design |
| Retail | Peak traffic 10–100x baseline on known dates; inventory truth across channels |
| Hospitality | Rate and availability parity across a dozen distribution channels |
| Logistics | The system's model of the physical world is always slightly wrong — reconciliation and eventual consistency, not transactional correctness |
| Energy | Safety-critical control; air-gapped or near-air-gapped OT |
| Government | The procurement cycle governs the timeline; accessibility is mandatory |
| Defence | Certification and clearance cost dominate everything else |
| Education | The academic calendar — releases happen between terms or not at all |
| Media | Rights windows decide what may be served, to whom, in which territory |
| Legal | Ethical walls: access boundaries that must be provable, not merely implemented |

## Anti-patterns

- **Recommending a replacement for the spine.** The customer has a core banking system, an EHR, a
  PMS. Proposing to replace it answers a question nobody asked and misreads the project.
- **Treating the integration protocol as an implementation detail.** HL7 v2 versus FHIR, or ISO
  20022 versus a proprietary file drop, changes the integration architecture, the team, and the
  timeline. It belongs in the recommendation, not in a later discovery phase.
- **Reading a certification regime as a compliance checklist.** GxP and DO-178C cap release
  cadence permanently. A recommendation of continuous deployment into a validated environment is
  not a stretch goal, it is a category error.
- **Assuming cloud-first below the OT boundary.** A plant floor, a substation and a classified
  enclave are not slow adopters; they are governed by safety certification and cannot be patched
  on a deployment schedule.
- **Using an explicit industry statement as the only vertical signal.** Most requirements never
  state one. The customer noun — patients, guests, subscribers, shipments — is the reliable signal.
- **Quoting a vendor market share as though it were durable.** Those figures move every year. The
  taxonomy, the protocol table and the layer model do not.

## Revisit triggers

- **§C (the spine):** revisit the moment the customer names their incumbent system — the specific
  vendor changes the integration protocol, the access path and often who controls the schedule.
- **§D (protocol):** revisit if the project scope crosses a vertical boundary. A logistics feature
  inside a retail programme inherits EDI and carrier integration, not just the commerce platform's.
- **§E (regulatory shape):** revisit on entry to any new market or jurisdiction, and whenever a
  regulator amends a registration regime — the shape can change from conduct to registration, which
  converts a design constraint into a launch blocker.
- **§F (OT boundary):** revisit if the scope moves from reporting on plant data to controlling
  plant equipment. Reading from a historian and writing to a PLC are different projects with
  different certification exposure.
- **Vendor tables generally:** treat any vendor or market-share statement in this document as
  stale after twelve months and re-verify before relying on it.

## As implemented in `index.html`

**Partially implemented.** `detectSignals()` recognises five verticals — `healthcare`, `finance`,
`ecommerce`, `retail` and `defense` — and uses them to raise compliance and security signals. That
is the whole of it.

Not implemented, and each is a decision point above: no system-of-record concept (§C), no
integration-protocol awareness (§D — the engine's only apparent protocol hits are false positives:
"PMs" as product managers and "Swift" the programming language), no registration/certification/
conduct distinction (§E), no OT/IT boundary reasoning (§F), and no data-gravity classification
(§G). Thirteen of the eighteen verticals have no signal at all.

Wiring any of this in means adding the customer-noun vocabulary from the Signals section above to
both engines in the same commit, per the repository's two-engines-one-behaviour rule.

## Sources

- [Global Industry Classification Standard (GICS) — structure and revisions](https://en.wikipedia.org/wiki/Global_Industry_Classification_Standard)
- [GICS Methodology, April 2026 — S&P Dow Jones Indices](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-gics.pdf)
- [NAICS structure: sectors and hierarchy](https://siccode.com/page/structure-of-naics-codes)
- [NAICS 2022 Manual (US)](https://www.naics.com/wp-content/uploads/2022/07/2022_NAICS_Manual.pdf)
- [NAICS 2027 revision — request for comments, Federal Register](https://www.federalregister.gov/documents/2024/12/20/2024-30060/statistical-policy-directive-no-8-north-american-industry-classification-system-naics-request-for)
- [Acute Care EHR Market Share 2026 (KLAS data) — HealthsystemCIO](https://healthsystemcio.com/2026/05/14/acute-care-ehr-market-share-2026/)
- [Core Banking Systems leaderboard — Juniper Research](https://www.juniperresearch.com/press/pressreleasescore-banking-systems-market-temenos-fis-mambu-revealed/)
- [Netcracker achieves TM Forum Ready for ODA status for BSS/OSS](https://www.netcracker.com/news/press-releases/netcracker-achieves-ready-for-oda-status-for-its-bss-oss-portfolio)
- [Vertical SaaS market and retention trends 2026 — Tracxn](https://tracxn.com/d/sectors/vertical-saas/__lBgpM-wMjFEil4mU-rLN7aipI6z-10MznvPZNS2l9UI)

**Deliberately excluded from this document:** the per-vertical vendor tables from the source
research (representative tools for each layer of each of the eighteen verticals). They are the part
that dates fastest — EHR and core-banking market shares move every year — and the part a reader
would most readily mistake for durable fact. The taxonomy in §A, the protocol table in §D and the
regulatory shapes in §E are stable for years; a vendor list is stale within one. If vendor
shortlists are wanted later they belong in `../alternatives-research/`, which is already the
convention for that kind of content, with a compiled-on date attached.
