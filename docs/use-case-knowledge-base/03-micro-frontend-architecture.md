# Micro-Frontend Architecture

**Status:** implemented — wired into `pickTradeoffs()` via the `microFrontend` signal.

**Domain:** Multiple independently-deployable frontend apps composed into one product, usually
owned by separate teams — e.g. a customer app, admin app, rider app under one design system.
Research date: August 2026.

## Business context

Directly informed by a real repository blueprint shared during this project's own development:
separate `frontend-host`, `customer`, `rider`, `admin`, and `b2b` frontend apps plus a shared
`design-system` package. This is exactly the pattern this document covers. Relevant when a
product spans multiple distinct user-facing surfaces owned by different teams, needing independent
deploy cadence without fragmenting the user experience.

## Signals / triggers

`micro-frontend` / `microfrontend` / `micro frontend`, `multiple frontend apps`, `separate customer
app and admin app` / `rider app` / `driver app`, `independent team deployment`, `independently
deployable UI`, `module federation`, `webpack module federation`, `single-spa`, `shell app` /
`host app` / `remote app`, `design system shared across apps`, `team-owned frontend`, `runtime
composition`, `Nx monorepo frontend`, `federated modules`.

## Decision points

### A. Composition/federation mechanism

- **Webpack Module Federation (MF 2.0, via webpack or Rspack)** — the dominant production pattern:
  apps expose/consume modules at runtime, with shared-dependency negotiation (singleton
  React/Angular, version ranges). Mature tooling, strong Nx/Angular Architects integration, but
  webpack-centric configuration complexity.
- **Vite / native ESM federation** — leverages native ES modules and import maps instead of a
  bundler-specific runtime; faster dev server, lighter config, but less mature shared-scope/version
  negotiation than webpack MF as of 2026.
- **single-spa** — a framework-agnostic runtime orchestrator (not a bundler plugin); mounts/
  unmounts independently built apps (any of React/Angular/Vue/vanilla) into a shell via lifecycle
  hooks and import maps. Good for polyglot-framework organizations.
- **iframe-based composition** — strongest isolation (styles, JS globals, crashes can't leak),
  simplest mental model, but poor UX (no shared routing/scroll, slow cross-frame comms, SEO/
  accessibility pain); reserved for embedding third-party/untrusted widgets, not a cohesive
  first-party product.
- **Nx monorepo with build-time composition** — all micro-frontends in one repo/build graph; Nx
  orchestrates incremental builds and affected-project detection, optionally layering Module
  Federation on top for runtime independence, or skipping runtime federation entirely.

### B. Shared design-system/component-library packaging

Typically a versioned npm package (or federated "shared" remote) published from a design-system
repo, consumed by all micro-frontends as a shared/singleton dependency in the federation config —
button/typography/token updates propagate without app-by-app rebuilds. This reintroduces a
coordination dependency across teams; many orgs pin to semver ranges and use contract/visual-
regression tests to decouple upgrade timing.

### C. State-sharing across federated apps

Options range from URL/query-string state (simplest, most decoupled) to custom browser events/a
shared pub-sub bus, to shared singleton stores (Redux/Zustand exposed as a federated shared module)
or Web Storage/cookies for auth/session. The stricter the shared-state coupling, the more the
"independent deployability" benefit erodes.

### D. "You probably don't need micro-frontends" case

For small teams (roughly under ~15-20 engineers) or a single product without genuinely separate
team-ownership boundaries, the operational overhead (multiple CI/CD pipelines, shared-dependency
negotiation, cross-team contracts, runtime composition debugging) outweighs the benefit. A modular
monolith with well-defined internal module boundaries (or an Nx/Turborepo monorepo without runtime
federation) gets most of the maintainability win at a fraction of the complexity.

## Anti-patterns

- **Premature adoption** — small teams splitting a young product into micro-frontends before real
  multi-team ownership pain exists, paying coordination tax with no payoff.
- **Duplicated framework bundles** — each remote shipping its own copy of React/Angular/lodash
  because shared-scope config wasn't set up correctly, bloating initial load. A frequently cited
  top anti-pattern.
- **Tightly-coupled shared state/shared global stores** that force synchronized deploys across
  "independent" apps, defeating the point of the architecture.
- **Inconsistent UX from divergent design-system versions**, and **over-fragmentation** (too many
  micro-frontends per team) causing orchestration/testing overhead to exceed team velocity gains.

## Reference implementations

- **Nx (Nrwl)** — canonical Module Federation + monorepo micro-frontend playbook used across many
  enterprise Angular/React shops.
- **single-spa** — framework-agnostic orchestrator with a documented recommended production setup.
- **CARS24 Engineering** — documented production use of Nx + Module Federation + Git submodules on
  AWS for hosting multiple micro-frontend apps.
- **Angular Architects** (`@angular-architects/module-federation`) — widely adopted toolchain for
  Angular-based multi-team, multi-framework rollouts.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `microFrontend` signal (or `enterprise && largeTeam && mobile
&& web` as an implicit trigger) — a dedicated trade-off card recommending Module Federation
(webpack/Rspack) with single-spa as the polyglot-framework alternative, explicitly warning off
adoption below ~15-20 engineers or single-team ownership.

## Sources

- [Nx: What is Micro Frontend Architecture?](https://nx.dev/docs/technologies/module-federation/concepts/micro-frontend-architecture)
- [PkgPulse: Module Federation 2.0 — webpack vs Rspack vs Vite (2026)](https://www.pkgpulse.com/guides/module-federation-2-webpack-rspack-vite-micro-frontends-2026)
- [ANGULARarchitects: Multi-Framework and -Version Micro Frontends with Module Federation](https://www.angulararchitects.io/blog/multi-framework-and-version-micro-frontends-with-module-federation-your-4-steps-guide/)
- [single-spa: The Recommended Setup](https://single-spa.js.org/docs/recommended-setup/)
- [micro-frontends.tech: Shared Dependencies](https://micro-frontends.tech/architecture/shared-dependencies/)
- [DEV (Florian Rappl): Top 10 Micro-Frontend Anti-Patterns](https://dev.to/florianrappl/top-10-micro-frontend-anti-patterns-3809)
- [DEV: Microfrontends — The Cost of Modularity and When Not to Use Them](https://dev.to/gabrielle_eduarda_776996b/microfrontends-the-cost-of-modularity-and-when-not-to-use-them-3b9n)
- [Nx: Module Federation and Nx](https://nx.dev/concepts/module-federation/module-federation-and-nx)
- [Cars24 Engineering: NX Module Federation](https://medium.com/cars24/nx-module-federation-a-scalable-solution-for-hosting-multiple-micro-frontend-applications-with-git-eee04fbd0b4f)
