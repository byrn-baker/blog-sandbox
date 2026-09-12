<!--
  SYNC IMPACT REPORT
  Version change: 1.0.0 → 1.1.0
  Modified principles:
    - IV. Least-Privilege Read-Only Telemetry — wording: NetFlow/IPFIX export
      and SuzieQ state capture named explicitly as read-only sources
    - Feature Scope & Guardrails — stack commitment updated (OTel Collector
      ingestion, VictoriaMetrics/VictoriaLogs, Grafana, SuzieQ state history,
      Part 8 in scope); geo-enrichment guardrails added
  Added sections:
    - VI. Collect Once, Reduce Deliberately — pipeline fidelity principle:
      OTel-first ingestion, deliberate documented reduction, measurable
      space-vs-fidelity claims, SuzieQ as Grafana source and fidelity
      cross-check, licensed pinned enrichment
    - Governance — compliance-review wording now covers principles I–VI
      (was "the five Core Principles")
  Removed sections: none
  Deferred items: none (build intent deferred — see Next Actions in summary)
-->

# Blog Observability Stack (blog-obs-stack) Constitution

## Core Principles

### I. Source-of-Truth First

Nautobot, fed exclusively by this git repository, is the single source of
truth for every device, interface, IP, prefix, VLAN, and VRF in the lab.
Feature work MUST express intended state as data (YAML/JSON templates, Design
Builder jobs, config contexts) committed to git; it MUST NOT rely on ad-hoc
state captured from live devices. When repo data and live state disagree, the
repo data is the intended state and live state is a defect to investigate.

Rationale: the project accompanies a public blog series demonstrating
Nautobot as SoT, so every slice must be reviewable, replayable, and auditable
from git alone.

### II. Verification Before Merge

Every feature slice MUST be proven against real tool output before it is
reported done: golden-config compliance checks against the generated intended
configs, read-back verification on the live lab (CML IOS-XE / EVE-NG EOS)
where behavior changes, and `make lint`/`make test` green for repository
code. Automated tests MUST exercise the actual Jinja renderers, Design
Builder jobs, and monitoring queries — not mocked stand-ins.

Rationale: the deliverable of this project is a working 28-device lab with an
observability stack, so unverified claims are indistinguishable from broken
configs. A change without passing verification is not complete.

### III. Zero-Drift Artifacts

Every generated artifact — intended configs, Grafana dashboards, Alerting
rules, VictoriaMetrics/VictoriaLogs configuration, ansible inventory —
MUST be produced from sources in this repository and MUST be regenerable by
a documented command. Hand-editing deployed artifacts is forbidden unless
the edit is first committed as a source change; regeneration MUST be
deterministic and idempotent so re-running it produces no diff.

### IV. Least-Privilege Read-Only Telemetry

Monitoring of the network MUST be read-only against the devices: SNMP
read-only polling, out-of-band exporters, and syslog/flow collection.
Features MUST NOT deploy write credentials or configuration-change paths to
production devices; any intended change flows through Nautobot + Golden
Config in git, never through the monitoring stack. Read-only sources include
SNMP polling, NetFlow/IPFIX export, syslog, and SuzieQ state capture from the
lab devices. Credentials and secrets MUST stay out of the repository
(ansible-vault or equivalent), and anything published in the blog series
MUST be sanitized.

### V. Reproducibility & Version Pinning

Every dependency — Helm charts, container images, exporters, Grafana
plugins, Python packages — MUST be pinned to an exact version and, where the
blog requires public replay, mirrored or vendored so the stack builds offline
from the repository alone. A feature slice MUST state its resource footprint
(CPU/RAM/disk on the Proxmox host) and MUST document how a reader of the blog
series can reproduce it.

## Feature Scope & Guardrails

- Scope: this project covers the observability stack for the 28-device SP
  MPLS/EVPN lab — metrics, logs, alerting, dashboards, and the Nautobot/ansible
  glue that provisions them — as published in the blog series (Part 7:
  Observability Stack, Part 8: SuzieQ State History, and downstream parts that
  extend it).
- Every feature MUST state which lab tier it touches: devices (Cisco IOS-XE on
  CML, Arista EOS on EVE-NG), k3s cluster services, or Nautobot
  configuration; out-of-scope touches MUST be flagged for review.
- Components MUST follow the stack established by the series — Nautobot as
  SoT, Golden Config for compliance, the OpenTelemetry Collector for
  ingestion, VictoriaMetrics/VictoriaLogs for telemetry storage, Grafana for
  visualization, SuzieQ for state history — unless a feature explicitly
  motivates a replacement in its spec and the constitution is amended.
- New telemetry MUST be labeled and documented consistently with existing
  conventions (job/instance labels, metric naming, log stream names) so
  dashboards and alerts remain composable.
- Geo-enrichment datasets (ipinfo, MaxMind, or similar) MUST be version-pinned
  with their license recorded; enrichment MUST be a clearly separated pipeline
  stage, never a hidden side effect, and MUST never block raw ingestion.
- Each feature MUST remain independently testable: a slice that cannot be
  verified on the live lab without deploying other in-flight slices is
  under-specified and MUST be reworked.

## Development Workflow

- Full Spec Kit SDD cycle is mandatory for every feature: `/speckit-specify`
  → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`, with the
  review gates in between; one feature per sequential branch
  (`###-feature-name` per the spec template).
- Specs MUST include acceptance scenarios written in Given/When/Then and
  measurable success criteria; a plan MUST map every task back to a spec
  requirement.
- Tasks MUST be completed in dependency order and each MUST include its
  verification step (lint, test, live check) before it is marked done.
- Docs travel with code: each feature MUST update the relevant
  `demo-lab/` design notes or series documentation so the repo remains the
  single narrative for the blog.
- Golden config templates, config contexts, and Nautobot jobs MUST be
  reviewed for intended-state changes alongside the feature that motivates
  them; a feature that changes topology or device config without updating
  those sources violates Principle I.

## Governance

- This constitution supersedes conflicting defaults and ad-hoc practice for
  all work in this project. Runtime development guidance lives in the Spec
  Kit templates and the workflow registry; where they conflict, this
  constitution wins.
- Amendments: any change to Core Principles requires a documented rationale,
  explicit user approval, and a migration note for in-flight features.
  Amendments are recorded here with a version bump per the policy below;
  PRs/reviews MUST verify compliance with the active version.
- Versioning: semver on the constitution — MAJOR for removal or redefinition
  of principles (backward-incompatible governance), MINOR for added
  principles/sections or materially expanded guidance, PATCH for
  clarifications and typo fixes.
- Compliance review: every spec, plan, and implementation review gate checks
  the Core Principles (I–VI) and the Feature Scope & Guardrails; a reviewer
  MUST call out violations explicitly rather than passing them silently.
- Complexity MUST be justified: each added component, chart, or exporter
  needs a stated reason and a deletion path; unexplained additions are
  rejected under Principle V.

### VI. Collect Once, Reduce Deliberately

Telemetry MUST be ingested raw and in full before any reduction: SNMP and
NetFlow/IPFIX exporters, SuzieQ state capture, and all other OpenTelemetry
sources MUST stream their complete payloads into the pipeline so no data is
lost before it is deliberately processed. All conversion of high-volume data
into time-series metrics — flow summaries, log-derived counters, SuzieQ
state snapshots — MUST be an explicit, documented pipeline stage with its
retention and aggregation policy stated, never a silent default. The
project's goal is to prove that large volumes of network data can be
converted to metrics to save storage space without losing fidelity, so every
space-saving claim in a feature MUST be backed by a measurement of both
bytes saved and fidelity retained, with the trade-off documented in the
spec.

Raw telemetry MUST remain queryable alongside the derived metrics: both
VictoriaMetrics (metrics) and VictoriaLogs (logs/events) are first-class
stores. The SuzieQ state database MUST be treated as a data source in its
own right and exposed to Grafana for graphing, and its state MUST be used as
the cross-check that derived metrics have not lost fidelity. Enrichment of
telemetry against external databases (for example ipinfo or MaxMind
geo-IP) MUST be done with a pinned version of a licensed dataset and MUST
keep the license and dataset revision recorded with the feature; enrichment
MUST NOT become a hard dependency of core metric collection.

Rationale: the central claim of this project — space-efficient,
fidelity-preserving network telemetry — is only demonstrable if raw data,
derived data, and the reduction logic between them are all inspectable.

**Version**: 1.1.0 | **Ratified**: 2026-09-07 | **Last Amended**: 2026-09-07
