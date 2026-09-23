"""Generate SuzieQ inventory from Nautobot and synchronize its runtime Secret.

The generated values contain device names, addresses, platform groupings, and
environment-variable references only. Resolved SSH credentials and the REST API
key are sent to Kubernetes over stdin and are never written to Git.
"""
import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import urllib.request
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[1]
ROLES = {"Border-Router", "CE-Router", "P-Router", "PE-Router", "Route-Reflector", "Leaf", "Spine"}
PLATFORM_GROUPS = {"cisco_iosxe": "CISCO_SSH", "arista_eos": "ARISTA_SSH"}
SECRET = "suzieq-credentials"


def fleet(response, selected=()):
    if response.get("errors") or not response.get("data", {}).get("devices"):
        raise ValueError("Nautobot query failed or returned no devices; preserving existing output")
    devices = []
    names = set()
    addresses = set()
    for source in response["data"]["devices"]:
        role = (source.get("role") or {}).get("name")
        platform = (source.get("platform") or {}).get("name")
        if role not in ROLES or platform not in PLATFORM_GROUPS:
            continue
        name = source["name"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Invalid device name")
        address = str(ipaddress.IPv4Interface(source["primary_ip4"]["address"]).ip)
        group = (source.get("secrets_group") or {}).get("name")
        if group != PLATFORM_GROUPS[platform]:
            raise ValueError(f"Unexpected SSH credential authority for {name}")
        if name in names or address in addresses:
            raise ValueError("Duplicate device or primary IPv4 address")
        names.add(name)
        addresses.add(address)
        devices.append({"name": name, "address": address, "platform": platform, "credential_group": group})
    if len(devices) != 28:
        raise ValueError(f"Expected 28 network devices, found {len(devices)}; preserving existing output")
    if selected:
        if set(selected) - names:
            raise ValueError("Selection contains an ineligible or missing device")
        devices = [device for device in devices if device["name"] in selected]
    return sorted(devices, key=lambda device: device["name"])


def inventory(devices):
    sources = []
    namespaces = []
    for group in sorted(set(device["credential_group"] for device in devices)):
        slug = group.lower().replace("_ssh", "")
        hosts = [
            {"url": "ssh://" + device["address"]}
            for device in devices if device["credential_group"] == group
        ]
        sources.append({"name": slug + "-network-fleet", "type": "native", "hosts": hosts})
        namespaces.append({
            "name": "sp-demo-lab", "source": slug + "-network-fleet",
            "device": "ssh-defaults", "auth": slug + "-credentials",
        })
    return {
        "sources": sources,
        "devices": [{"name": "ssh-defaults", "transport": "ssh", "port": 22, "ignore-known-hosts": True}],
        "auths": [
            {
                "name": group.lower().replace("_ssh", "") + "-credentials",
                "username": "env:SUZIEQ_" + group.replace("_SSH", "_USERNAME"),
                "password": "env:SUZIEQ_" + group.replace("_SSH", "_PASSWORD"),
            }
            for group in sorted(set(device["credential_group"] for device in devices))
        ],
        "namespaces": namespaces,
    }


def query():
    url = os.environ["NAUTOBOT_URL"].rstrip("/") + "/api/graphql/"
    request = urllib.request.Request(
        url,
        data=json.dumps({"query": (ROOT / "queries/network_fleet.gql").read_text()}).encode(),
        headers={"Authorization": "Token " + os.environ["NAUTOBOT_TOKEN"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def resolve_credentials():
    code = r'''
import json
from nautobot.dcim.models import Device
rows={}
for platform,group in [('cisco_iosxe','CISCO_SSH'),('arista_eos','ARISTA_SSH')]:
    device=Device.objects.filter(platform__name=platform,secrets_group__name=group).order_by('name').first()
    assert device is not None
    rows[group]={
      'username':device.secrets_group.get_secret_value('Generic','username',obj=device),
      'password':device.secrets_group.get_secret_value('Generic','password',obj=device),
    }
print(json.dumps(rows))
'''
    result = subprocess.run(
        ["docker", "exec", "nautobot_docker_compose-nautobot-1", "nautobot-server", "shell",
         "--interface", "python", "--command", code],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError("Nautobot SSH credential resolution failed; details suppressed")
    try:
        rows = json.loads(next(line for line in result.stdout.splitlines() if line.startswith("{")))
    except (StopIteration, json.JSONDecodeError) as exc:
        raise RuntimeError("Nautobot SSH credential resolution returned no usable result") from exc
    if set(rows) != set(PLATFORM_GROUPS.values()) or any(
        not values.get("username") or not values.get("password") for values in rows.values()
    ):
        raise RuntimeError("Nautobot SSH credential authority is incomplete")
    return rows


def secret_state():
    result = subprocess.run(
        ["kubectl", "-n", "observability", "get", "secret", SECRET, "--ignore-not-found", "-o", "json"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError("Cannot read SuzieQ Secret state")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def sync_secret(credentials):
    previous = secret_state()
    prior_data = previous.get("data", {})
    api_key = base64.b64decode(prior_data["API_KEY"]).decode() if prior_data.get("API_KEY") else secrets.token_urlsafe(32)
    values = {"API_KEY": api_key}
    for group, resolved in credentials.items():
        prefix = "SUZIEQ_" + group.replace("_SSH", "_")
        values[prefix + "USERNAME"] = resolved["username"]
        values[prefix + "PASSWORD"] = resolved["password"]
    data = {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}
    revision = previous.get("metadata", {}).get("annotations", {}).get("telemetry.lab/credential-revision")
    if data == prior_data and revision:
        return revision
    revision = str(uuid.uuid4())
    manifest = {
        "apiVersion": "v1", "kind": "Secret",
        "metadata": {
            "name": SECRET, "namespace": "observability",
            "labels": {"app.kubernetes.io/managed-by": "nautobot-suzieq-generator"},
            "annotations": {"telemetry.lab/credential-revision": revision},
        },
        "type": "Opaque", "data": data,
    }
    result = subprocess.run(
        ["kubectl", "apply", "--server-side", "--field-manager=nautobot-suzieq-generator", "-f", "-"],
        input=json.dumps(manifest), capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError("SuzieQ Secret synchronization failed; details suppressed")
    return revision


def atomic_yaml(path, document):
    text = "# Generated by blog-sandbox/telemetry/generate_suzieq.py. No credential values.\n"
    text += yaml.safe_dump(document, sort_keys=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        output.write(text)
        temporary = output.name
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--select", nargs="*", default=[])
    parser.add_argument("--sync-secret", action="store_true")
    args = parser.parse_args()
    all_devices = fleet(query())
    devices = [device for device in all_devices if not args.select or device["name"] in args.select]
    if args.select and len(devices) != len(set(args.select)):
        raise ValueError("Selection contains an ineligible or missing device")
    previous = yaml.safe_load(Path(args.output).read_text()) if Path(args.output).exists() else {}
    revision = (previous or {}).get("credentialRevision")
    if args.sync_secret:
        revision = sync_secret(resolve_credentials())
    if not revision:
        raise ValueError("Credential revision absent; run once with --sync-secret before publication")
    atomic_yaml(args.output, {"credentialRevision": revision, "inventory": inventory(devices)})
    print(f"Generated SuzieQ inventory for {len(devices)} devices without credential values")


if __name__ == "__main__":
    main()
