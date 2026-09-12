# 06: Services Distribution

## Design Philosophy

Services are spread across the three DCs to generate meaningful cross-site
traffic that traverses the MPLS L3VPN core. This creates realistic monitoring
scenarios: replication lag under congestion, failover when a site goes dark,
log pipeline stalls when connectivity degrades.

## Cluster topology: one stretched cluster, not three

There is a single K3s cluster stretched across all three datacenters. It is not
three independent clusters. Every node sits on the VXLAN/EVPN VLAN 100
segment (`10.100.0.0/24`) stretched across DC-A, DC-B and DC-C. Host IPv6
uses `fd10:a:100::/64`; Kubernetes Pod and Service networks remain IPv4.

The control plane is three server nodes running embedded etcd, all in DC-A:

| Node | DC | VLAN 100 IP | K3s role |
|------|----|-------------|----------|
| DCA-k3s-m1 | DC-A | 10.100.0.10 | server (cluster-init) |
| DCA-k3s-m2 | DC-A | 10.100.0.11 | server |
| DCA-k3s-m3 | DC-A | 10.100.0.12 | server |
| DCB-k3s-w1 | DC-B | 10.100.0.20 | agent |
| DCB-k3s-w2 | DC-B | 10.100.0.21 | agent |
| DCB-k3s-w3 | DC-B | 10.100.0.22 | agent |
| DCC-k3s-w4 | DC-C | 10.100.0.30 | agent |
| DCC-k3s-w5 | DC-C | 10.100.0.31 | agent |
| DCC-k3s-w6 | DC-C | 10.100.0.32 | agent |

All three etcd members remain in DC-A after the earlier cross-site latency
and lease failures. Flooded and spaced pings behaved differently, but those
observations did not isolate scheduling as the sole cause. The subsequent
QEMU and GRO fixes improved packet delivery; residual latency under storage
load still needs investigation before moving etcd back across sites.
The current control plane does not survive losing DC-A.

There is no API VIP or keepalived. Agents register against m1 at
`10.100.0.10:6443`. The leaf anycast gateway `10.100.0.1` provides routing,
not API endpoint failover.

DCA-DNS is a Server-role device on the same VLAN 100 segment but is not a
cluster member. It runs standalone BIND (see below).

## Lab DNS: BIND on DCA-DNS, generated from Nautobot

DCA-DNS (10.100.0.53) is the lab's authoritative DNS server for the
`sandbox.lab` zone. Every record is generated from Nautobot: the Ansible role
queries all devices and their primary IPs and renders the forward zone plus
reverse zones from that data. Device forward records use Nautobot primary IPs, currently management
addresses; the explicit `ns1` record uses `10.100.0.53`. DNS is updated from
the source of truth when the playbook runs,
and a topology change is reflected by re-running the role, never by hand-editing
a zone file.

## Automation: Ansible sourced entirely from Nautobot

Host configuration (the bond, K3s, BIND) is managed by Ansible, and Ansible
takes everything from Nautobot. There is no static inventory file. The Nautobot
dynamic inventory pulls the Server-role devices, reaches them over their
management IPs, and builds the `k3s_servers` / `k3s_agents` / `dns_servers`
groups from a Git-synced K3s config context. Per-node data (management IP, DC,
VLAN 100 addresses, K3s role) all resolve from the model. See
`06a-ansible-automation.md` for the full automation architecture.

---

## Future demonstration workloads

The examples below are proposed scenarios, not the deployed application
inventory. Current collection uses VictoriaMetrics and an OTel SNMP collector;
Prometheus, Loki, MinIO and the sample application stacks below are not claims
of deployment. Concrete example endpoints need matching Services and placement
before use. See [the verified rebuild record](10-server-network-rebuild.md).

## Service Placement Matrix

| Namespace | Service | DC1 | DC2 | DC3 | Cross-DC traffic |
|-----------|---------|-----|-----|-----|------------------|
| `app` | nginx-frontend | ✓ primary | ✓ standby |: | Client failover |
| `app` | api-server (Flask/Express) | ✓ | ✓ | ✓ | Any-DC routing |
| `data` | PostgreSQL | ✓ primary | ✓ streaming replica |: | WAL replication DC1→DC2 |
| `data` | Redis | ✓ primary |: | ✓ replica | Async replication DC1→DC3 |
| `infra` | CoreDNS | ✓ | ✓ | ✓ | Local resolution |
| `monitoring` | Prometheus | ✓ central |: |: | Scrapes all DCs |
| `monitoring` | Grafana | ✓ |: |: | Queries Prometheus |
| `monitoring` | Loki |: | ✓ |: | All DCs push logs here |
| `monitoring` | OTEL Collector | ✓ | ✓ | ✓ | Forward to DC1 Prometheus |
| `storage` | MinIO |: |: | ✓ | Backup writes from DC1/DC2 |

---

## Service Details

### nginx-frontend (DC1 primary, DC2 standby)

Simple nginx serving a static site or reverse-proxying to the API. Demonstrates:
- HTTP blackbox probes from Prometheus
- Failover scenario when DC1 goes down
- Request latency metrics

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-frontend
  namespace: app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
        resources:
          requests: { cpu: 100m, memory: 64Mi }
          limits: { cpu: 500m, memory: 128Mi }
```

### api-server (all DCs)

Lightweight REST API that queries the database and Redis. Generates varied
response codes and latencies you can inject for testing alerts.

```yaml
# Flask app that:
# - Connects to PostgreSQL (DC1 primary or DC2 replica)
# - Reads/writes Redis (DC1 primary or DC3 replica)
# - Exposes /metrics for Prometheus
# - Exposes /health for blackbox probes
```

### PostgreSQL (DC1 primary, DC2 replica)

Streaming replication generates continuous WAL traffic across the MPLS core:

```yaml
# DC1: PostgreSQL primary
# DC2: PostgreSQL streaming replica
#   primary_conninfo = 'host=10.100.0.11 port=5432 ...'
#   (traffic: DC2 → CE2 → SPE2 → core → SPE1 → CE1 → DC1)
```

Monitoring points:
- `pg_stat_replication`: replication lag in bytes/seconds
- Connection count
- Query latency

### Redis (DC1 primary, DC3 replica)

Async replication: less sensitive to latency but interesting for partition
scenarios:

```bash
# On DC3 Redis replica:
replicaof 10.100.0.12 6379
# Traffic flows: DC3 → CE3 → SPE3 → core → SPE1 → CE1 → DC1
```

### Prometheus (DC1: central)

Scrapes all nodes and services across all DCs:

```yaml
# prometheus.yml scrape targets
scrape_configs:
  - job_name: 'node-dc1'
    static_configs:
      - targets:
        - '10.100.0.10:9100'
        - '10.100.0.11:9100'
        - '10.100.0.12:9100'

  - job_name: 'node-dc2'
    static_configs:
      - targets:
        - '192.168.200.10:9100'
        - '192.168.200.11:9100'
        - '192.168.200.12:9100'

  - job_name: 'node-dc3'
    static_configs:
      - targets:
        - '10.100.0.10:9100'   # Example node on shared VLAN 100
        - '10.100.0.11:9100'

  - job_name: 'api-servers'
    static_configs:
      - targets:
        - '10.100.0.10:8080'   # DC1 API
        - '192.168.200.10:8080'   # DC2 API
        - '10.100.0.30:8080'   # Example DC3 API

  - job_name: 'postgres'
    static_configs:
      - targets:
        - '10.100.0.11:9187'   # postgres_exporter DC1
        - '192.168.200.11:9187'   # postgres_exporter DC2
```

### Loki (DC2)

All DCs ship logs to Loki in DC2 via Promtail or OTEL Collector:

```yaml
# Promtail config on DC1 nodes
clients:
  - url: http://192.168.200.10:3100/loki/api/v1/push
    # Traffic: DC1 → CE1 → SPE1 → core → SPE2 → CE2 → DC2 Loki
```

### MinIO (DC3: object storage / backup target)

S3-compatible storage for backups:

```bash
# DC1 PostgreSQL backup ships to DC3 MinIO:
pg_dump mydb | aws s3 cp - s3://backups/pg/$(date +%Y%m%d).sql \
  --endpoint-url http://10.100.0.12:9000
# (traffic routes through MPLS core to DC3)
```

### OTEL Collector (all DCs)

Local collectors aggregate metrics and traces, forward to central Prometheus:

```yaml
exporters:
  prometheusremotewrite:
    endpoint: "http://10.100.0.10:9090/api/v1/write"
    # DC2/DC3 collectors send metrics across the MPLS core to DC1
```

---

## Cross-DC Traffic Summary

```
┌────────┐          ┌────────┐          ┌────────┐
│  DC1   │          │  DC2   │          │  DC3   │
│        │◄─WAL────►│        │          │        │
│ PG pri │  replic  │ PG rep │          │        │
│        │          │        │          │        │
│ Redis  │─────────────────────────────►│ Redis  │
│ primary│  async replication           │ replica│
│        │          │        │          │        │
│ Prom   │◄─scrape──│ nodes  │◄─scrape──│ nodes  │
│        │          │        │          │        │
│ nodes  │──logs───►│ Loki   │◄──logs───│ nodes  │
│        │          │        │          │        │
│ API    │          │ API    │          │ API    │
│        │──backup──────────────────────►│ MinIO  │
└────────┘          └────────┘          └────────┘
```

---

## Kubernetes Manifests Structure

```
demo-lab/
└── manifests/
    ├── base/                    # Shared across all DCs
    │   ├── namespace.yaml
    │   ├── node-exporter.yaml
    │   └── otel-collector.yaml
    ├── dc1/
    │   ├── nginx-frontend.yaml
    │   ├── api-server.yaml
    │   ├── postgresql-primary.yaml
    │   ├── redis-primary.yaml
    │   ├── prometheus.yaml
    │   └── grafana.yaml
    ├── dc2/
    │   ├── nginx-frontend-standby.yaml
    │   ├── api-server.yaml
    │   ├── postgresql-replica.yaml
    │   └── loki.yaml
    └── dc3/
        ├── api-server.yaml
        ├── redis-replica.yaml
        └── minio.yaml
```
