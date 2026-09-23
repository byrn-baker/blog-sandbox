"""Prepare, deploy, and verify the approved EOS sFlow fleet rollout."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

import canary_control as control


control.EVIDENCE = Path(__file__).parent / "evidence" / "sflow-fleet-20260923"
CHANGE = "part8-eos-sflow-fleet-20260923"
CANARY = "DCA-Leaf02"
INTENDED_JOB = "ab420817-1d1f-4d56-a319-382be6970919"
BACKUP_JOB = "f2033b99-24cd-4949-be4e-ed79d8178850"
COMPLIANCE_JOB = "6ffd11a2-7e95-4b93-b900-e134eaee1d4d"
PLAN_JOB = "82a6fe32-9897-4acc-ba8b-f6d0849d9717"
DEPLOY_JOB = "7c91d376-a0e9-4178-96fe-7b80954ced04"


def shell(code, timeout=180):
    result = subprocess.run(
        [
            "docker", "exec", "nautobot_docker_compose-nautobot-1",
            "nautobot-server", "shell", "--interface", "python", "--command", code,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return json.loads(next(line for line in result.stdout.splitlines() if line.startswith(("[", "{"))))


def inventory():
    rows = control.api("dcim/devices/?platform=arista_eos&limit=100")["results"]
    assert len(rows) == 15, f"Expected 15 EOS devices, found {len(rows)}"
    return sorted(rows, key=lambda row: row["name"])


def refresh():
    devices = inventory()
    ids = [row["id"] for row in devices]
    control.record("inventory", [{"name": row["name"], "id": row["id"]} for row in devices])
    control.run(INTENDED_JOB, {"device": ids}, "intended")
    control.run(BACKUP_JOB, {"device": ids, "commit_message": "EOS fleet sFlow fresh backups"}, "backup")
    control.run(COMPLIANCE_JOB, {"device": ids}, "compliance")


PLAN_CODE = r'''
import json
from datetime import timedelta
from django.utils import timezone
from nautobot_golden_config.models import GoldenConfig

required = [
    'sflow vrf MGMT-VRF destination 192.168.3.241',
    'sflow vrf MGMT-VRF source-interface Management1',
    'sflow sample 16384',
    'sflow polling-interval 20',
    'sflow run',
]
rows = []
query = GoldenConfig.objects.filter(device__platform__name='arista_eos').select_related('device')
for g in query.order_by('device__name'):
    assert g.intended_last_success_date and g.backup_last_success_date and g.compliance_last_success_date
    assert g.compliance_last_success_date >= max(g.intended_last_success_date, g.backup_last_success_date)
    assert timezone.now() - g.intended_last_success_date < timedelta(minutes=30)
    assert all(line in g.intended_config.splitlines() for line in required)
    current = set(g.backup_config.splitlines())
    missing = [line for line in required if line not in current]
    assert not missing or missing == required, (g.device.name, missing)
    rows.append({
        'name': g.device.name,
        'device': str(g.device.pk),
        'commands': '\n'.join(missing) + ('\n' if missing else ''),
        'already_configured': not missing,
        'intended_at': str(g.intended_last_success_date),
        'backup_at': str(g.backup_last_success_date),
        'compliance_at': str(g.compliance_last_success_date),
    })
assert len(rows) == 15
print(json.dumps(rows))
'''


def prepare_plans():
    rows = shell(PLAN_CODE)
    control.record("reviewed-deltas", rows)
    pending = [row for row in rows if not row["already_configured"]]
    assert len(pending) == 14, f"Expected one existing canary and 14 pending devices, found {len(pending)}"
    assert [row["name"] for row in rows if row["already_configured"]] == ["DCA-Leaf01"]
    for row in pending:
        print(row["name"] + ": " + ", ".join(row["commands"].splitlines()), flush=True)
        control.run(
            PLAN_JOB,
            {
                "device": [row["device"]],
                "plan_type": "manual",
                "commands": row["commands"],
                "change_control_id": CHANGE,
                "debug": False,
            },
            "plan-" + row["name"],
        )


def selected(name):
    reviewed = json.loads((control.EVIDENCE / "reviewed-deltas.json").read_text())
    expected = {row["name"]: row for row in reviewed}
    assert name in expected and not expected[name]["already_configured"]
    plans = control.api("plugins/golden-config/config-plan/?change_control_id=" + CHANGE + "&limit=100")["results"]
    matches = [
        plan for plan in plans
        if plan["device"]["id"] == expected[name]["device"]
        and plan["config_set"].strip() == expected[name]["commands"].strip()
    ]
    assert len(matches) == 1, name
    assert not matches[0].get("deploy_result"), name + " already deployed"
    return matches[0]


def deploy(name):
    endpoint = json.loads(subprocess.check_output([
        "kubectl", "get", "endpoints", "telemetry-canary", "-n", "observability", "-o", "json"
    ]))
    ports = {port["port"] for subset in endpoint.get("subsets", []) for port in subset.get("ports", [])}
    assert 6343 in ports, "sFlow receiver endpoint is absent"
    plan = selected(name)
    approved = control.api("extras/statuses/?name=Approved&limit=100")["results"]
    assert len(approved) == 1
    control.api(
        "plugins/golden-config/config-plan/" + plan["id"] + "/",
        {"status": approved[0]["id"]},
        method="PATCH",
    )
    control.record(
        "approval-" + name,
        {
            "device": name,
            "plan": plan["id"],
            "authorization": "Operator requested EOS sFlow fleet deployment on 2026-09-23",
            "receiver_endpoint": sorted(ports),
        },
    )
    control.run(
        DEPLOY_JOB,
        {"config_plan": [plan["id"]], "fail_job_on_task_failure": True, "debug": False},
        "deploy-" + name,
    )


VERIFY_CODE = r'''
import concurrent.futures, json, logging
from nautobot.dcim.models import Device
from netmiko import ConnectHandler

logging.disable(logging.CRITICAL)
names = NAMES

def collect(device):
    row = {'name': device.name, 'address': str(device.primary_ip4.host), 'commands': {}}
    try:
        username = device.secrets_group.get_secret_value('Generic', 'username', obj=device)
        password = device.secrets_group.get_secret_value('Generic', 'password', obj=device)
        with ConnectHandler(
            device_type='arista_eos', host=row['address'], username=username, password=password,
            secret=password, session_log=None, conn_timeout=15, auth_timeout=20, banner_timeout=30,
        ) as connection:
            connection.enable()
            for command in [
                'show sflow', 'show sflow interfaces',
                'show running-config | section sflow',
                'show startup-config | section sflow',
                'show bgp evpn summary',
            ]:
                row['commands'][command] = connection.send_command(command, read_timeout=45)
            row['cli_errors'] = [
                command for command, output in row['commands'].items()
                if '% Invalid' in output or '% Error' in output
            ]
    except Exception as exc:
        row['error_type'] = type(exc).__name__
        row['error'] = str(exc).splitlines()[0][:200]
    return row

devices = Device.objects.filter(name__in=names).select_related('primary_ip4', 'secrets_group').order_by('name')
with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(names))) as pool:
    rows = list(pool.map(collect, devices))
print(json.dumps(rows))
'''


def verify(names, label):
    rows = shell(VERIFY_CODE.replace("NAMES", repr(names)), timeout=360)
    control.record("verify-" + label, rows)
    for row in rows:
        commands = row.get("commands", {})
        running = commands.get("show running-config | section sflow", "")
        startup = commands.get("show startup-config | section sflow", "")
        status = commands.get("show sflow", "")
        result = {
            "name": row["name"],
            "address": row.get("address"),
            "error_type": row.get("error_type"),
            "cli_errors": row.get("cli_errors"),
            "running": "sflow run" in running,
            "startup": "sflow run" in startup,
            "exporting": "Running: yes" in status and "192.168.3.241" in status,
        }
        print(json.dumps(result), flush=True)
        assert not result["error_type"] and not result["cli_errors"]
        assert result["running"] and result["startup"] and result["exporting"]


def acceptance():
    devices = inventory()
    names = {row["id"]: row["name"] for row in devices}
    rules = control.api("plugins/golden-config/compliance-rule/?limit=100")["results"]
    matches = [rule for rule in rules if rule["display"] == "arista_eos - flow_export"]
    assert len(matches) == 1
    compliance = [
        {
            "device": names[row["device"]["id"]],
            "compliance": row["compliance"],
            "missing": row["missing"],
            "extra": row["extra"],
        }
        for row in control.api("plugins/golden-config/config-compliance/?limit=1000")["results"]
        if row["rule"]["id"] == matches[0]["id"] and row["device"]["id"] in names
    ]
    compliance.sort(key=lambda row: row["device"])
    assert len(compliance) == 15 and all(row["compliance"] for row in compliance)

    verified = json.loads((control.EVIDENCE / "verify-fleet.json").read_text())
    expected = {row["address"]: row["name"] for row in verified}
    query = "_time:30m AND flow.type:sflow_5 | stats by (flow.sampler_address) count() as records"
    request = urllib.request.Request(
        "http://127.0.0.1:19428/select/logsql/query",
        data=urllib.parse.urlencode({"query": query}).encode(),
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        rows = [json.loads(line) for line in response.read().splitlines() if line]
    received = {
        row["flow.sampler_address"]: int(row["records"])
        for row in rows if row.get("flow.sampler_address") in expected
    }
    assert set(received) == set(expected), sorted(set(expected) - set(received))
    result = {
        "window": "30m",
        "flow_type": "sflow_5",
        "compliance": compliance,
        "victorialogs": [
            {"device": expected[address], "sampler_address": address, "records": received[address]}
            for address in sorted(received)
        ],
    }
    control.record("acceptance", result)
    print(json.dumps({"compliant": len(compliance), "samplers_in_victorialogs": len(received)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["refresh", "plans", "deploy", "verify", "acceptance"])
    parser.add_argument("names", nargs="*")
    args = parser.parse_args()
    if args.action == "refresh":
        refresh()
    elif args.action == "plans":
        prepare_plans()
    elif args.action == "deploy":
        assert len(args.names) == 1, "Deploy exactly one Config Plan per job"
        deploy(args.names[0])
    elif args.action == "verify":
        names = args.names or [row["name"] for row in inventory()]
        verify(names, "fleet" if not args.names else "-".join(names))
    else:
        acceptance()
