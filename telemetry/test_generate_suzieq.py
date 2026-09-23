import base64
import json

import pytest
import yaml

from generate_suzieq import fleet, inventory, sync_secret


def response(count=28):
    devices = []
    for index in range(count):
        eos = index >= 13
        devices.append({
            "name": ("Leaf" if eos else "PE") + str(index),
            "role": {"name": "Leaf" if eos else "PE-Router"},
            "platform": {"name": "arista_eos" if eos else "cisco_iosxe"},
            "secrets_group": {"name": "ARISTA_SSH" if eos else "CISCO_SSH"},
            "primary_ip4": {"address": f"192.168.3.{index + 20}/24"},
        })
    return {"data": {"devices": devices}}


def test_inventory_is_sorted_and_uses_env_references():
    devices = fleet(response())
    document = inventory(devices)
    assert len(devices) == 28
    assert [source["name"] for source in document["sources"]] == ["arista-network-fleet", "cisco-network-fleet"]
    assert all("password" not in host["url"] and "username" not in host["url"] for source in document["sources"] for host in source["hosts"])
    assert {auth["password"] for auth in document["auths"]} == {
        "env:SUZIEQ_ARISTA_PASSWORD", "env:SUZIEQ_CISCO_PASSWORD"
    }


def test_fleet_rejects_wrong_count_and_credential_authority():
    with pytest.raises(ValueError, match="Expected 28"):
        fleet(response(27))
    broken = response()
    broken["data"]["devices"][0]["secrets_group"]["name"] = "ARISTA_SSH"
    with pytest.raises(ValueError, match="credential authority"):
        fleet(broken)


def test_failed_or_empty_query_is_rejected():
    with pytest.raises(ValueError, match="preserving"):
        fleet({"errors": [{"message": "failed"}]})
    with pytest.raises(ValueError, match="preserving"):
        fleet({"data": {"devices": []}})


def test_secret_sync_preserves_api_key_and_hides_values(monkeypatch):
    prior = {
        "metadata": {"annotations": {"telemetry.lab/credential-revision": "old"}},
        "data": {"API_KEY": base64.b64encode(b"stable-key").decode()},
    }
    monkeypatch.setattr("generate_suzieq.secret_state", lambda: prior)
    captured = {}

    def run(command, **kwargs):
        captured.update(json.loads(kwargs["input"]))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("generate_suzieq.subprocess.run", run)
    revision = sync_secret({
        "CISCO_SSH": {"username": "cisco-user", "password": "cisco-pass"},
        "ARISTA_SSH": {"username": "arista-user", "password": "arista-pass"},
    })
    assert revision != "old"
    assert base64.b64decode(captured["data"]["API_KEY"]) == b"stable-key"
    assert "cisco-pass" not in yaml.safe_dump(captured)
