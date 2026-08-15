# SP Demo Lab Blog Series — Outline

## Premise

You have a Proxmox host running CML with 28 virtual network devices (13 IOS-XE,
15 Arista EOS) and 8 K3s VMs. Management interfaces are up on 192.168.3.0/24.
Nothing else is configured. This series takes you from that starting point to a
fully monitored multi-tenant SP network with NetClaw acting as your NOC.

## Prerequisites (assumed done, not covered)

- Proxmox host with CML VM deployed
- 28 network nodes in CML: RR1-2, SP1-4, SPE1-3, CE1-3, BORDER1, 3×DC fabrics (5 Arista each)
- 8 K3s VMs created on Proxmox bridges (vmbr100/200/300)
- All management interfaces configured per `01-addressing.md` and reachable via SSH
- A Linux workstation/VM on the management network (where NetClaw will live)

## Series Arc

### Part 1 — Nautobot: Your Source of Truth (Day 0) ✅ PUBLISHED

**Goal**: Deploy Nautobot and populate it with the complete lab topology so every
subsequent step pulls from SoT rather than spreadsheets.

- Deploy Nautobot 3.2.1 via Docker Compose with Design Builder, BGP Models,
  IGP Models, and Golden Config plugins
- Idempotent design job: bulk-create all 28 devices with interfaces, IPs (248),
  cabling (41 cables), VRFs, ISIS instances (10), BGP peerings (45)
- Everything queryable via GraphQL — one source of truth for all downstream tools

### Part 2 — Golden Config: Intended Configurations (Day 1) ✅ PUBLISHED

**Goal**: Wire Golden Config to the blog-sandbox repo and generate intended
configurations for all 28 devices from SoT data — no spreadsheets, no Ansible.

- Link Git repo (Jinja templates) to Nautobot Golden Config
- Modular Jinja2 templates pulling ISIS/MPLS/BGP data via GraphQL + config contexts
- Generate intended configs for all 28 devices (SP core + DC fabric) with one button
- Covers: ISIS underlay, MPLS LDP, iBGP VPNv4/v6, VRFs with RT import/export,
  eBGP PE-CE, DC eBGP underlay, EVPN overlay, VXLAN VTEPs

### Part 3 — Deploy and Verify: Bringing the Network Up (Day 2) ✅ PUBLISHED

**Goal**: Push intended configs to all 28 live devices using Golden Config's
Config Plans workflow, then verify every layer of the network.

- Prerequisites: device credentials (per-platform secrets groups), primary IPs,
  network reachability from Nautobot worker
- Compliance rules: 20 features, 32 rules (15 Cisco IOS-XE, 17 Arista EOS)
- Config Plans workflow: Backup → Compliance → Generate Plans → Approve → Deploy
- Deployment order: P/RR/Border → PEs → CEs → DC fabric
- Verification: ISIS adjacencies, MPLS LDP neighbors, BGP VPNv4 sessions,
  PE-CE eBGP, DC eBGP underlay + EVPN overlay
- Post-deployment compliance baseline

### Part 4 — K3s Clusters and Application Workloads (Day 3)

**Goal**: Bootstrap K3s in each DC and deploy distributed services that generate
real cross-site traffic.

- Bootstrap 3 K3s clusters (1 server + 2 agents each)
- Deploy: PostgreSQL primary (DC-A) + replica (DC-B), API servers (all DCs),
  MinIO backup (DC-C), Redis cache (DC-A)
- Verify: cross-DC replication working, API serving from all DCs

### Part 5 — Observability Stack: The Eyes and Ears (Day 4)

**Goal**: Deploy the full observability pipeline so every device, link, and
application emits telemetry into a queryable data plane.

- Deploy Convergence stack on the management VM (Docker Compose)
- Pull device inventory from Nautobot (`--mode nautobot`) — no manual target lists
- OTel Collector: SNMP polling all 28 devices + syslog receiver
- Prometheus: node-exporter on K3s nodes, blackbox cross-DC probes, app metrics
- Loki: log aggregation from all DCs via OTel
- Grafana: Network / Security / NetClaw boards on :3300
- Alertmanager: alert rules for BGPPeerDown, InterfaceDown, CrossDCLatencyHigh,
  HighPacketLoss, MPLSLabelExhaustion
- Verify: all targets up, dashboards populated, test alert fires on synthetic condition

### Part 6 — SuzieQ: State History for Investigations (Day 5)

**Goal**: Deploy the state-history plane so investigations can ask "what changed?"
and look backward in time across the entire network.

- Enable `device_telemetry.state.suzieq` in convergence.yaml
- Apply: `convergence-telemetry-apply.sh` renders inventory from Nautobot targets
- `docker compose --profile suzieq up -d`
- Verify: `smoke-suzieq.sh` passes, BGP/route/interface tables populated
- Test time-travel: shut a link, wait, query `view=changes`
- Why this matters for the AI NOC: SuzieQ gives the agent temporal context that
  Prometheus alone cannot — "BGP was Established 5 minutes ago, now it's not,
  and here's the route table diff"

### Part 7 — NetClaw: Building the Agentic NOC (Day 6)

**Goal**: Deploy NetClaw as an AI agent that receives alerts, investigates
autonomously using every data plane we've built, and produces actionable
root cause analysis — no human touching a CLI.

**The agentic architecture:**

- **Alert ingestion** — Alertmanager webhook → NetClaw alert-receiver
- **Investigation tiers** — T0 (acknowledge + enrich), T1 (query metrics/logs),
  T2 (deep investigation: SuzieQ state history, Nautobot topology correlation,
  multi-hop blast radius analysis)
- **MCP tooling** — NetClaw uses MCP servers to talk to:
  - Nautobot (topology, device relationships, VRF membership, BGP peering data)
  - SuzieQ (historical state: BGP table before/after, route changes, interface flaps)
  - Prometheus (current metrics: utilization, latency, error rates)
  - Loki (correlated log events across devices and time windows)
- **Reasoning chain** — The agent doesn't just query; it reasons through the
  problem: "BGP down on SPE1 → check ISIS adjacency on upstream link → link is
  down → check interface counters → CRC errors climbing → physical layer issue"
- **Diary output** — Investigation results posted as structured diary entries
  with root cause, affected services, blast radius, and recommended remediation

**Setup steps:**

- Install NetClaw (recommended profile + convergence)
- Configure investigation policies: which alerts get which tier
- Wire alert-receiver to Alertmanager webhook
- Configure MCP servers: Nautobot endpoint, SuzieQ API, Prometheus query API
- Ensure guardian-claw member permissions for investigations
- Point `SUZIEQ_API_URL` at the live REST API
- Verify: manual alert injection → investigation runs → diary entry appears

### Part 8 — Failure Scenarios: The AI NOC in Action (Day 7+)

**Goal**: Run realistic failure scenarios and show the full agentic investigation
loop — from alert firing to root cause posted in the diary.

Each scenario demonstrates a different investigation pattern:

- **Scenario 1: CE link failure** — DC isolation cascade
  - What fires: BGPPeerDown (PE-CE), CrossDCLatencyHigh (blackbox probes)
  - Agent reasoning: queries Nautobot for topology → identifies single point of
    failure → checks SuzieQ for route withdrawal timeline → correlates with
    interface down event in Loki → posts blast radius (which VRFs lost reachability)
  - Diary: "CE1 GigabitEthernet2 down at 14:23:07, BGP peer 172.16.1.0 withdrawn,
    CUST-A VRF isolated from DC-A, 3 K3s nodes unreachable"

- **Scenario 2: Core link failure** — IGP reconvergence + MPLS reroute
  - Agent reasoning: ISIS topology change detected via SuzieQ → new SPF path
    computed → MPLS labels redistributed → verifies forwarding recovered →
    reports transient impact window

- **Scenario 5: Bandwidth saturation** — QoS and congestion
  - Agent reasoning: latency alert → checks interface utilization in Prometheus →
    identifies congested link → queries SuzieQ for traffic shift → correlates
    with upstream IGP event that shifted traffic

- **Scenario 7: VRF withdrawal** — Catastrophic partition
  - Agent reasoning: multiple BGP alerts cluster → queries Nautobot for RT
    relationships → maps full blast radius across all affected PEs and CEs →
    identifies config change as root cause via compliance diff

For each: what fired, how the agent reasoned through it, what data sources it
queried (and in what order), and the final diary entry.

### Part 9 — Closed-Loop Remediation: From Detection to Fix (Bonus)

**Goal**: Close the full loop — the AI NOC detects drift, Golden Config holds
the intended state, and the system can remediate with human approval.

- NetClaw detects config drift via compliance alerts
- Agent queries Nautobot Golden Config for the intended vs. actual diff
- Agent identifies which compliance feature is non-compliant and why
- Remediation workflow: NetClaw posts recommendation → operator approves →
  Config Plans deploys the fix → compliance re-runs → diary updated with resolution
- `suzieq_assert` before and after a remediation push (state validation)
- The full circle: SoT → config → monitor → detect drift → investigate → recommend → fix → verify
- Discussion: where to draw the line on autonomous remediation vs. human-in-the-loop

---

## Relationship to existing design docs (01–07)

The design docs are the **what**. This series is the **how**. Each blog post
references the relevant design doc but doesn't duplicate it:

| Blog Part | References |
|-----------|------------|
| Part 1 | 01-addressing (all IPs/ASNs), all topology docs |
| Part 2 | 02-sp-core-topology, 03-vrf-design, 04-datacenter-design |
| Part 3 | 02/03/04 (deployment + verification of all layers) |
| Part 4 | 05-cml-proxmox-integration, 06-services-distribution |
| Part 5 | 07-monitoring-scenarios (alert definitions) |
| Part 6 | 07-monitoring-scenarios (state history) |
| Part 7 | 07-monitoring-scenarios (investigation architecture) |
| Part 8 | 07-monitoring-scenarios (all failure scenarios) |
| Part 9 | Nautobot golden-config + NetClaw closed-loop |

---

## The Agentic NOC Narrative (Series Throughline)

The first half of the series (Parts 1–4) builds the infrastructure: SoT, config,
network, workloads. The second half (Parts 5–9) builds the *intelligence layer*
on top of it. The payoff is not "we have dashboards" — it's "we have an AI agent
that can autonomously investigate network incidents using real network state."

The arc should feel like:
- Parts 1–3: "We built a network the right way" (SoT-driven, repeatable)
- Part 4: "We gave it something to carry" (real traffic, real failure domain)
- Part 5: "We gave it eyes" (metrics, logs, alerts)
- Part 6: "We gave it memory" (historical state, temporal queries)
- Part 7: "We gave it a brain" (the agent, the reasoning, the MCP tooling)
- Part 8: "We proved it works" (real failures, real investigations)
- Part 9: "We closed the loop" (detect → investigate → recommend → fix → verify)

---

## Target audience

Network engineers who can configure an IGP and know what EVPN is, but want to
see how SoT-driven automation + AI-assisted monitoring works end to end on a
realistic topology. Not a "hello world" — a reference implementation they can
reproduce on their own Proxmox/CML setup.

Secondary audience: platform engineers and SREs curious about agentic operations
applied to network infrastructure — how MCP servers, investigation tiers, and
tool-use patterns translate from "chatbot" to "autonomous NOC engineer."