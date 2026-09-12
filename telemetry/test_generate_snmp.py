import copy
import json
import sys
import subprocess
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import generate_snmp as g


def response():
    return {"data": {"devices": [{"name": name, "role": {"name": role},
        "platform": {"name": platform}, "primary_ip4": {"address": ip + "/24"},
        "location": {"name": "DC-A"}, "config_context": {"snmp": {
            "ro_community": "fixture-only-secret", "acl_source": "192.168.3.0/24", "contact": "fixture"}}}
        for name, role, platform, ip in [("CE1", "CE-Router", "cisco_iosxe", "192.168.3.60"),
            ("DCA-Leaf01", "Leaf", "arista_eos", "192.168.3.32")]]}}


def test_deterministic_and_secret_free():
    r = response()
    a = g.values(g.fleet(r))
    r["data"]["devices"].reverse()
    assert a == g.values(g.fleet(r))
    assert "fixture-only-secret" not in yaml.safe_dump(a)
    assert len(a["alternateConfig"]["receivers"]) == 2
    delays = [r["initial_delay"] for r in a["alternateConfig"]["receivers"].values()]
    assert len(set(delays)) == 2
    assert all(0 < int(d[:-1]) < 60 for d in delays)
    assert a["extraEnvs"][0]["valueFrom"]["secretKeyRef"]["name"] == g.SECRET


@pytest.mark.parametrize("change", ["remove", "role", "platform", "context", "contact"])
def test_membership_follows_source(change):
    r = response()
    d = r["data"]["devices"][0]
    if change == "remove":
        r["data"]["devices"].pop(0)
    elif change == "role":
        d["role"]["name"] = "Server"
    elif change == "platform":
        d["platform"]["name"] = "unsupported"
    elif change == "context":
        d["config_context"] = {}
    else:
        d["config_context"]["snmp"].pop("contact")
    assert [d["name"] for d in g.fleet(r)] == ["DCA-Leaf01"]


@pytest.mark.parametrize("r", [{}, {"errors": [{"message": "failure"}]}, {"data": {"devices": []}}])
def test_failed_query_preserves_output(tmp_path, monkeypatch, r):
    target = tmp_path / "values.yaml"
    target.write_text("previous valid configuration\n")
    monkeypatch.setattr(g, "query", lambda: r)
    monkeypatch.setattr(sys, "argv", ["generate_snmp.py", "--output", str(target)])
    with pytest.raises(ValueError):
        g.main()
    assert target.read_text() == "previous valid configuration\n"


def test_duplicate_and_changed_acl_rejected():
    r = response()
    r["data"]["devices"].append(copy.deepcopy(r["data"]["devices"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        g.fleet(r)
    r = response()
    r["data"]["devices"][0]["config_context"]["snmp"]["acl_source"] = "192.168.100.0/24"
    with pytest.raises(ValueError, match="egress"):
        g.fleet(r)


def test_canary_and_scalar_counter_semantics():
    devices = g.fleet(response(), ["CE1"])
    assert len(devices) == 1
    rec = g.receiver(devices[0])
    assert rec["collection_interval"] == "60s"
    assert rec["attributes"]["interface"]["oid"] == "1.3.6.1.2.1.2.2.1.2"
    assert rec["attributes"]["if_name"]["oid"] == "1.3.6.1.2.1.31.1.1.1.1"
    assert rec["metrics"]["snmp_device_uptime_ticks"]["scalar_oids"][0]["oid"].endswith(".3.0")
    assert rec["metrics"]["snmp_interface_in_octets_total"]["column_oids"][0]["oid"] == "1.3.6.1.2.1.31.1.1.1.6"
    with pytest.raises(ValueError, match="ineligible"):
        g.fleet(response(), ["missing"])


def test_serialized_context():
    r = response()
    r["data"]["devices"][0]["config_context"] = json.dumps(r["data"]["devices"][0]["config_context"])
    assert len(g.fleet(r)) == 2


def test_secret_sync_is_idempotent_and_rotation_marker_is_not_secret(monkeypatch):
    devices = g.fleet(response())
    calls = []
    stored = {}

    def run(args, **kwargs):
        calls.append(args)
        if "get" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps(stored) if stored else "", "")
        stored.update(json.loads(kwargs["input"]))
        return subprocess.CompletedProcess(args, 0, "configured", "")

    monkeypatch.setattr(g.subprocess, "run", run)
    first = g.sync_secret(devices)
    second = g.sync_secret(devices)
    assert first == second
    assert sum("apply" in args for args in calls) == 1
    devices[0]["community"] = "rotated-fixture-only"
    assert g.sync_secret(devices) != first
    assert sum("apply" in args for args in calls) == 2
    assert "fixture" not in first


def test_failed_secret_write_leaves_generated_values(tmp_path, monkeypatch):
    target = tmp_path / "values.yaml"
    target.write_text("previous valid configuration\n")
    monkeypatch.setattr(g, "query", response)
    def fail(_):
        raise RuntimeError("Secret synchronization failed")
    monkeypatch.setattr(g, "sync_secret", fail)
    monkeypatch.setattr(sys, "argv", ["generate_snmp.py", "--output", str(target), "--sync-secret"])
    with pytest.raises(RuntimeError):
        g.main()
    assert target.read_text() == "previous valid configuration\n"
