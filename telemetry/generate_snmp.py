"""Generate non-secret Collector values from Nautobot; resolve credentials separately.

Requires Python 3 and PyYAML. CLI credentials are read from environment only.
Nothing from a failed/empty query is published. Kubernetes Secret writes use
stdin and server-side apply, without a last-applied annotation or secret logs.
"""
import argparse
import base64
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import uuid

import yaml
from network_dashboard import dashboard

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"Border-Router", "CE-Router", "P-Router", "PE-Router", "Route-Reflector", "Leaf", "Spine"}
PLATFORMS = {"cisco_iosxe", "arista_eos"}
SECRET = "network-snmp-credentials"


def fleet(response, selected=()):
    if response.get("errors") or not response.get("data", {}).get("devices"):
        raise ValueError("Nautobot query failed or returned no devices; preserving existing output")
    result = []
    names, addresses, keys = set(), set(), set()
    for source in response["data"]["devices"]:
        if (source.get("role") or {}).get("name") not in ROLES:
            continue
        if (source.get("platform") or {}).get("name") not in PLATFORMS:
            continue
        ctx = source.get("config_context") or {}
        if isinstance(ctx, str):
            ctx = json.loads(ctx)
        snmp = ctx.get("snmp", {})
        if not all(snmp.get(k) for k in ("ro_community", "acl_source", "contact")):
            continue
        name = source["name"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Invalid device name")
        address = str(ipaddress.IPv4Interface(source["primary_ip4"]["address"]).ip)
        key = "SNMP_" + name.upper().replace("-", "_")
        if name in names or address in addresses or key in keys:
            raise ValueError("Duplicate device or primary IPv4 address")
        names.add(name)
        addresses.add(address)
        keys.add(key)
        network = ipaddress.IPv4Network(snmp["acl_source"])
        if network != ipaddress.IPv4Network("192.168.3.0/24"):
            raise ValueError("SNMP ACL changed; verify collector egress before generation")
        result.append(dict(name=name, address=address, platform=source["platform"]["name"],
                           site=source["location"]["name"], community=snmp["ro_community"],
                           contact=snmp["contact"], key=key))
    if not result:
        raise ValueError("No eligible SNMP devices; preserving existing output")
    if selected:
        if set(selected) - names:
            raise ValueError("Canary selection contains an ineligible or missing device")
        result = [d for d in result if d["name"] in selected]
    return sorted(result, key=lambda d: d["name"])


def receiver(device):
    metrics = {"snmp_device_uptime_ticks": {"description": "sysUpTime in hundredths of a second; wraps after about 497 days",
               "unit": "1", "gauge": {"value_type": "int"},
               "scalar_oids": [{"oid": "1.3.6.1.2.1.1.3.0"}]}}
    columns = {
        "in_octets_total": ("1.3.6.1.2.1.31.1.1.1.6", "By", True),
        "out_octets_total": ("1.3.6.1.2.1.31.1.1.1.10", "By", True),
        "in_errors_total": ("1.3.6.1.2.1.2.2.1.14", "1", True),
        "out_errors_total": ("1.3.6.1.2.1.2.2.1.20", "1", True),
        "in_discards_total": ("1.3.6.1.2.1.2.2.1.13", "1", True),
        "out_discards_total": ("1.3.6.1.2.1.2.2.1.19", "1", True),
        "oper_status": ("1.3.6.1.2.1.2.2.1.8", "1", False),
        "admin_status": ("1.3.6.1.2.1.2.2.1.7", "1", False),
        "speed_mbps": ("1.3.6.1.2.1.31.1.1.1.15", "1", False),
    }
    for name, (oid, unit, counter) in columns.items():
        metric = {"unit": unit, "column_oids": [{"oid": oid, "attributes": [
            {"name": "interface"}, {"name": "if_index"}]}]}
        metric["sum" if counter else "gauge"] = ({"aggregation": "cumulative", "monotonic": True,
            "value_type": "int"} if counter else {"value_type": "int"})
        metrics["snmp_interface_" + name] = metric
    return {"endpoint": "udp://" + device["address"] + ":161", "version": "v2c",
            "community": "${env:" + device["key"] + "}", "collection_interval": "60s", "timeout": "3s",
            "attributes": {"interface": {"oid": "1.3.6.1.2.1.31.1.1.1.1"},
                           "if_index": {"indexed_value_prefix": "if"}}, "metrics": metrics}


def values(devices, credential_revision=None):
    config = {
        "receivers": {},
        "processors": {"memory_limiter": {"check_interval": "1s", "limit_mib": 384, "spike_limit_mib": 64},
                       "batch": {"timeout": "5s", "send_batch_size": 2048, "send_batch_max_size": 4096}},
        "exporters": {"otlp_http/victoriametrics": {
            "metrics_endpoint": "http://vmsingle-victoria-metrics-k8s-stack.observability.svc:8428/opentelemetry/v1/metrics",
            "compression": "gzip", "timeout": "15s",
            "sending_queue": {"enabled": True, "num_consumers": 2, "queue_size": 1000},
            "retry_on_failure": {"enabled": True, "initial_interval": "5s", "max_interval": "30s", "max_elapsed_time": "300s"}}},
        "extensions": {"health_check": {"endpoint": "${env:MY_POD_IP}:13133"}},
        "service": {"extensions": ["health_check"], "pipelines": {},
                    "telemetry": {"metrics": {"readers": [{"pull": {"exporter": {"prometheus": {
                        "host": "${env:MY_POD_IP}", "port": 8888}}}}]}}}}
    # Keep the existing short-retention query/alert path and retain the same
    # samples in a separately budgeted 547-day VictoriaMetrics store.
    config["exporters"]["otlp_http/snmp_history"] = copy.deepcopy(config["exporters"]["otlp_http/victoriametrics"])
    config["exporters"]["otlp_http/snmp_history"]["metrics_endpoint"] = "http://snmp-metrics.observability.svc:8428/opentelemetry/v1/metrics"
    envs = []
    rules = []
    for device in devices:
        name = device["name"]
        rec, proc = "snmp/" + name, "resource/" + name
        config["receivers"][rec] = receiver(device)
        config["processors"][proc] = {"attributes": [{"key": k, "value": v, "action": "upsert"}
            for k, v in {"device": name, "platform": device["platform"], "site": device["site"],
                         "management_ip": device["address"], "telemetry_source": "snmp",
                         "job": "snmp", "instance": device["address"]}.items()]}
        config["service"]["pipelines"]["metrics/" + name] = {"receivers": [rec],
            "processors": ["memory_limiter", proc, "batch"], "exporters": ["otlp_http/victoriametrics", "otlp_http/snmp_history"]}
        envs.append({"name": device["key"], "valueFrom": {"secretKeyRef": {"name": SECRET, "key": device["key"]}}})
        rules.append({"alert": "NetworkSnmpDeviceStale", "record": "", "expr": 'absent_over_time(snmp_device_uptime_ticks{device="'+name+'"}[3m])',
                      "for": "2m", "labels": {"severity": "warning", "device": name},
                      "annotations": {"summary": name + " has no fresh SNMP uptime sample"}})
    return {
        "fullnameOverride": "otel-snmp", "mode": "deployment", "replicaCount": 1,
        "image": {"repository": "docker.io/otel/opentelemetry-collector-contrib", "tag": "0.154.0",
                  "digest": "sha256:b3079f45e19bdb7326bf49cdddce6cf60dfd865138db39f2733ea48ab17bc4cb"},
        "command": {"name": "otelcol-contrib"}, "alternateConfig": config,
        "extraEnvs": envs, "serviceAccount": {"automountServiceAccountToken": False},
        "resources": {"requests": {"cpu": "100m", "memory": "192Mi"}, "limits": {"memory": "512Mi"}},
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]}},
        "ports": {**{p: {"enabled": False} for p in ["otlp", "otlp-http", "jaeger-compact", "jaeger-thrift", "jaeger-grpc", "zipkin"]},
                  "metrics": {"enabled": True}},
        "rollout": {"strategy": "Recreate"},
        "podAnnotations": ({"telemetry.lab/credential-revision": credential_revision} if credential_revision else {}),
        "extraManifests": [
            {"apiVersion": "v1", "kind": "ConfigMap",
             "metadata": {"name": "network-snmp-dashboard", "namespace": "observability", "labels": {"grafana_dashboard": "1"}},
             "data": {"network-snmp.json": json.dumps(dashboard(len(devices)), indent=2)}},
            {"apiVersion": "v1", "kind": "ConfigMap",
             "metadata": {"name": "network-snmp-datasource", "namespace": "observability", "labels": {"grafana_datasource": "1"}},
             "data": {"network-snmp.yaml": yaml.safe_dump({"apiVersion": 1, "datasources": [{
                 "name": "Network SNMP (547 days)", "uid": "network-snmp", "type": "prometheus", "access": "proxy",
                 "url": "http://snmp-metrics.observability.svc:8428", "isDefault": False,
                 "jsonData": {"httpMethod": "POST", "timeInterval": "60s"}, "editable": False}]})}},
            {"apiVersion": "operator.victoriametrics.com/v1beta1", "kind": "VMServiceScrape",
             "metadata": {"name": "otel-snmp", "namespace": "observability"},
             "spec": {"selector": {"matchLabels": {"app.kubernetes.io/instance": "otel-snmp"}},
                      "endpoints": [{"port": "metrics", "interval": "30s"}]}},
            {"apiVersion": "operator.victoriametrics.com/v1beta1", "kind": "VMRule",
             "metadata": {"name": "network-snmp", "namespace": "observability"},
             "spec": {"groups": [{"name": "network-snmp-freshness", "rules": rules}]}}
        ]}


def atomic_yaml(path, document):
    text = "# Generated by blog-sandbox/telemetry/generate_snmp.py. No credential values.\n" + yaml.safe_dump(document, sort_keys=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
        out.write(text)
        temp = out.name
    os.chmod(temp, 0o644)
    os.replace(temp, path)


def sync_secret(devices):
    secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": SECRET, "namespace": "observability",
        "labels": {"app.kubernetes.io/managed-by": "nautobot-snmp-generator"}}, "type": "Opaque",
        "data": {d["key"]: base64.b64encode(d["community"].encode()).decode() for d in devices}}
    existing = subprocess.run(["kubectl", "-n", "observability", "get", "secret", SECRET, "--ignore-not-found", "-o", "json"],
                              text=True, capture_output=True, timeout=30)
    if existing.returncode:
        raise RuntimeError("Cannot read credential synchronization state; preserving existing output")
    previous = json.loads(existing.stdout) if existing.stdout.strip() else {}
    revision = previous.get("metadata", {}).get("annotations", {}).get("telemetry.lab/credential-revision")
    if previous.get("data") == secret["data"] and revision:
        return revision
    revision = str(uuid.uuid4())
    secret["metadata"]["annotations"] = {"telemetry.lab/credential-revision": revision}
    result = subprocess.run(["kubectl", "apply", "--server-side", "--field-manager=nautobot-snmp-generator", "-f", "-"],
                            input=json.dumps(secret), text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Credential synchronization failed; preserving generated values (details suppressed)")
    return revision


def query():
    url = os.environ["NAUTOBOT_URL"].rstrip("/") + "/api/graphql/"
    request = urllib.request.Request(url, data=json.dumps({"query": (ROOT / "queries/network_fleet.gql").read_text()}).encode(),
        headers={"Authorization": "Token " + os.environ["NAUTOBOT_TOKEN"], "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--canary", nargs="*", default=[])
    parser.add_argument("--sync-secret", action="store_true")
    args = parser.parse_args()
    response = query()
    all_devices = fleet(response)
    selected = fleet(response, args.canary)
    document = values(selected)
    if args.sync_secret:
        document["podAnnotations"] = {"telemetry.lab/credential-revision": sync_secret(all_devices)}
    atomic_yaml(args.output, document)
    print(f"Generated {len(selected)} receivers without credential values")


if __name__ == "__main__":
    main()
