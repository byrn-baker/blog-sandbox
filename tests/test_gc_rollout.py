"""Isolated runner logic tests. External Django/Nornir services are explicitly mocked.

Target-worker integration is a separate release gate; these tests issue no SSH,
Nautobot API calls or device writes.
"""
import copy
import importlib.util
import json
import sys
import types
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "jobs" / "gc_rollout"


@pytest.fixture
def modules(monkeypatch):
    external = ["django", "django.db", "django.utils", "django.utils.timezone", "nautobot",
                "nautobot.apps", "nautobot.apps.jobs", "nautobot.dcim", "nautobot.dcim.models",
                "nautobot.extras", "nautobot.extras.models", "nautobot_plugin_nornir",
                "nautobot_plugin_nornir.constants", "nornir", "nautobot_golden_config",
                "nautobot_golden_config.jobs", "nautobot_golden_config.models",
                "nautobot_golden_config.nornir_plays", "nautobot_golden_config.nornir_plays.config_deployment",
                "nautobot_golden_config.utilities", "nautobot_golden_config.utilities.constant",
                "nautobot_golden_config.utilities.helper"]
    for name in external:
        module = types.ModuleType(name)
        module.__path__ = []
        module.__getattr__ = lambda name: MagicMock(name=name)
        monkeypatch.setitem(sys.modules, name, module)
    for name in external:
        if "." in name:
            parent, child = name.rsplit(".", 1)
            setattr(sys.modules[parent], child, sys.modules[name])
    class Job:
        def __init__(self):
            self.logger = Mock()
            self.user = types.SimpleNamespace(pk="operator", username="operator", is_superuser=False)
            self.job_result = types.SimpleNamespace(pk="execution", job_model_id="executor-model")
    sys.modules["nautobot.apps.jobs"].Job = Job
    sys.modules["nautobot_golden_config.jobs"].BackupJob = Job
    sys.modules["nautobot_golden_config.jobs"].ComplianceJob = Job
    sys.modules["django.db"].transaction = types.SimpleNamespace(atomic=nullcontext)
    sys.modules["django.utils.timezone"].now = lambda: datetime(2026, 9, 27, tzinfo=timezone.utc)
    sys.modules["nautobot_golden_config.utilities.constant"].ENABLE_POSTPROCESSING = False
    prefix = "rollout_under_test"
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            monkeypatch.delitem(sys.modules, name)
    spec = importlib.util.spec_from_file_location(prefix, SOURCE / "__init__.py", submodule_search_locations=[str(SOURCE)])
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, prefix, package)
    spec.loader.exec_module(package)
    return types.SimpleNamespace(jobs=package, **{name: sys.modules[prefix + "." + name]
                               for name in ("state", "manifest", "backend", "verify")})


@pytest.fixture
def prepared(modules, monkeypatch):
    m = modules.manifest
    monkeypatch.setattr(m, "backup_paths", lambda *args: [])
    def validate_source(repo, approved):
        if repo.current_head != approved["commit"]:
            raise ValueError("Source HEAD changed")
    monkeypatch.setattr(m, "validate_source", validate_source)
    spec = {"plan_ids": ["plan-1", "plan-2", "plan-3", "plan-4"],
            "source_repository": "repo", "source_commit": "a" * 40, "ci_evidence": "CI run 123",
            "rollback_reference": "reviewed rollback", "change_control_id": "change1",
            "canaries": ["CE1", "Leaf1"], "parallel_canaries": True, "wave_size": 1,
            "ntp_server": "192.168.3.242", "timeout_seconds": 1200, "poll_seconds": 20,
            "feature_ids": ["ntp"]}
    plans = []
    for index, (name, driver) in enumerate((("CE1", "cisco_iosxe"), ("CE2", "cisco_iosxe"),
                                          ("Leaf1", "arista_eos"), ("Leaf2", "arista_eos")), 1):
        platform = types.SimpleNamespace(network_driver=driver)
        device = types.SimpleNamespace(pk=name, name=name, platform=platform, platform_id=driver,
                                       primary_ip4="192.0.2.1/24", primary_ip6=None)
        features = Mock()
        features.values_list.return_value = ["ntp"]
        plans.append(types.SimpleNamespace(pk=f"plan-{index}", device=device, device_id=name,
                    config_set="ntp server vrf MGMT-VRF 192.168.3.242", plan_type="intended",
                    plan_result_id="generated", change_control_id="change1", feature=features,
                    deploy_result_id=None, status=types.SimpleNamespace(name="Not Approved")))
    m.ConfigPlan.objects.restrict.return_value.filter.return_value.select_related.return_value = plans
    m.GitRepository.objects.restrict.return_value.get.return_value = types.SimpleNamespace(pk="repo", name="blog-sandbox", current_head="a"*40)
    m.GoldenConfig.objects.get.return_value = types.SimpleNamespace(backup_last_success_date=datetime.now(timezone.utc),
                 intended_last_success_date=datetime.now(timezone.utc), backup_config="ntp server 192.0.2.2",
                 intended_config="ntp server vrf MGMT-VRF 192.168.3.242")
    monkeypatch.setattr(m, "rules_snapshot", lambda *a: [{"id": "rule-"+p, "platform_id": p, "feature_id": "ntp"}
                                                      for p in sorted(a[0])])
    monkeypatch.setattr(m, "version", lambda k: {"nautobot": "3.2.1", "nautobot-golden-config": "3.0.7"}.get(k, "3.0.0"))
    return spec, plans


def test_parallel_canaries_precede_fleet(modules, prepared):
    manifest = modules.manifest.build("user", prepared[0])
    assert manifest["waves"] == [["CE1", "Leaf1"], ["Leaf2"], ["CE2"]]


def test_sequential_canaries_are_separate(modules, prepared):
    prepared[0]["parallel_canaries"] = False
    assert modules.manifest.build("user", prepared[0])["waves"][:2] == [["CE1"], ["Leaf1"]]


@pytest.mark.parametrize("field,value", [("parallel_canaries", "true"), ("wave_size", 0), ("wave_size", True),
    ("timeout_seconds", 1801), ("poll_seconds", 1), ("canaries", ["CE1"]), ("canaries", ["CE1", "CE2"]),
    ("plan_ids", ["same", "same"]), ("source_commit", "b"*40), ("ci_evidence", ""), ("feature_ids", [])])
def test_bad_spec_rejected(modules, prepared, field, value):
    prepared[0][field] = value
    with pytest.raises(ValueError):
        modules.manifest.build("user", prepared[0])


@pytest.mark.parametrize("field,value", [("deploy_result_id", "already-used"), ("config_set", "hostname wrong"),
                                        ("change_control_id", "different")])
def test_ineligible_plan_rejected(modules, prepared, field, value):
    setattr(prepared[1][0], field, value)
    with pytest.raises(ValueError):
        modules.manifest.build("user", prepared[0])


def test_digest_binds_policy_and_commands(modules, prepared):
    manifest = modules.manifest.build("user", prepared[0])
    original = modules.manifest.digest(manifest)
    changed = copy.deepcopy(manifest)
    changed["spec"]["parallel_canaries"] = False
    assert modules.manifest.digest(changed) != original
    changed = copy.deepcopy(manifest)
    changed["plans"][0]["config_set"] += "\nno ntp authenticate"
    assert modules.manifest.digest(changed) != original


@pytest.mark.parametrize("status,row,expected", [
    ("Clock is synchronized, stratum 5", "*~192.168.3.242 192.168.3.1 4 11 64 37 2.9 1.1 0.6", (True, True)),
    ("synchronised to NTP server (192.168.3.242) at stratum 5", "*192.168.3.242 192.168.3.1 4 u 11 64 37 2.9 1.1 0.6", (True, True)),
    ("unsynchronised", "*192.168.3.242 192.168.3.1 4 u 11 64 37 2.9 1.1 0.6", (True, False)),
    ("Clock is synchronized", "+192.168.3.242 192.168.3.1 4 11 64 37 2.9 1.1 0.6", (True, False)),
    ("Clock is synchronized", "*192.168.3.242 192.168.3.1 4 11 64 0 2.9 1.1 0.6", (False, False)),
    ("Clock is synchronized", "*192.168.3.243 192.168.3.1 4 11 64 37 2.9 1.1 0.6", (False, False)),
])
def test_ntp_states(modules, status, row, expected):
    assert modules.verify.peer_state(status, row, "192.168.3.242") == expected


@pytest.fixture
def execution(modules, monkeypatch):
    j = modules.jobs
    manifest = {"plans": [{"device": "CE1"}, {"device": "CE2"}], "waves": [["CE1"], ["CE2"]]}
    ledger = {"manifest": manifest, "approval_digest": modules.manifest.digest(manifest), "execution_job": None,
              "stage": "prepared", "cancel_requested": False, "expires_at": "2026-09-28T00:00:00+00:00",
              "events": [], "completed_waves": [], "approval": None}
    @contextmanager
    def locked(_):
        yield ledger
    monkeypatch.setattr(j.state, "locked", locked)
    monkeypatch.setattr(j.state, "read", lambda _: copy.deepcopy(ledger))
    monkeypatch.setattr(j, "permission_check", Mock())
    monkeypatch.setattr(j, "validate_current", Mock())
    j.JobResult.objects.filter.return_value.exclude.return_value.iterator.return_value = iter([])
    calls = []
    monkeypatch.setattr(j, "verify_wave", lambda *a, **k: calls.append(("baseline" if k.get("baseline") else "verify", a[3])))
    def deploy(*a):
        ledger["stage"] = "deploying"
        calls.append(("deploy", a[3]))
    monkeypatch.setattr(j, "deploy", deploy)
    monkeypatch.setattr(j, "refresh_evidence", lambda *a: calls.append(("evidence", a[3])))
    return j.ExecuteGCRollout(), ledger, calls


def test_execute_order(modules, execution):
    job, ledger, calls = execution
    assert job.run("run", ledger["approval_digest"], "operator-approved")["stage"] == "completed"
    assert calls == [("baseline", ["CE1", "CE2"]), ("baseline", ["CE1"]), ("deploy", ["CE1"]),
                     ("verify", ["CE1"]), ("evidence", ["CE1"]), ("baseline", ["CE2"]),
                     ("deploy", ["CE2"]), ("verify", ["CE2"]), ("evidence", ["CE2"])]


@pytest.mark.parametrize("mutation", ["digest", "expired", "duplicate", "canceled"])
def test_claim_refusal_never_deploys(modules, execution, mutation):
    job, ledger, calls = execution
    approval = ledger["approval_digest"]
    if mutation == "digest": approval = "wrong"
    if mutation == "expired": ledger["expires_at"] = "2020-01-01T00:00:00+00:00"
    if mutation == "duplicate": ledger["execution_job"] = "existing"
    if mutation == "canceled": ledger["cancel_requested"] = True
    with pytest.raises(ValueError): job.run("run", approval, "approved")
    assert calls == []


def test_changed_plan_stops_before_claim(modules, execution, monkeypatch):
    job, ledger, calls = execution
    monkeypatch.setattr(modules.jobs, "validate_current", Mock(side_effect=ValueError("Plan changed")))
    with pytest.raises(ValueError): job.run("run", ledger["approval_digest"], "approved")
    assert ledger["execution_job"] is None and not calls


def test_failed_canary_prevents_fleet(modules, execution, monkeypatch):
    job, ledger, calls = execution
    def verify(*a, **k):
        if not k.get("baseline"): raise TimeoutError("unsynchronized")
    monkeypatch.setattr(modules.jobs, "verify_wave", verify)
    with pytest.raises(TimeoutError): job.run("run", ledger["approval_digest"], "approved")
    assert calls == [("deploy", ["CE1"])]
    assert ledger["stage"] == "failed"


def test_ambiguous_push_requires_reconciliation(modules, execution, monkeypatch):
    job, ledger, calls = execution
    def deploy(*a):
        ledger["stage"] = "deploying"
        raise ConnectionError("worker/connection interrupted")
    monkeypatch.setattr(modules.jobs, "deploy", deploy)
    with pytest.raises(ConnectionError): job.run("run", ledger["approval_digest"], "approved")
    assert ledger["stage"] == "needs_reconciliation"
    assert ledger["completed_waves"] == []


def test_cancel_after_canary_prevents_fleet(modules, execution, monkeypatch):
    job, ledger, calls = execution
    def evidence(*a): ledger["cancel_requested"] = True
    monkeypatch.setattr(modules.jobs, "refresh_evidence", evidence)
    with pytest.raises(modules.verify.RolloutCanceled): job.run("run", ledger["approval_digest"], "approved")
    assert [v for k, v in calls if k == "deploy"] == [["CE1"]]
    assert ledger["stage"] == "canceled"


def test_cancel_job_preserves_inflight_stage(modules, execution):
    _, ledger, _ = execution
    ledger["stage"] = "deploying"
    job = modules.jobs.CancelGCRollout()
    job.user.is_superuser = True
    assert job.run("run", "operator stop")["cancel_requested"]
    assert ledger["stage"] == "deploying"


def test_reconcile_refuses_active_worker(modules, execution):
    _, ledger, _ = execution
    ledger.update(stage="needs_reconciliation", execution_job="existing")
    job = modules.jobs.ReconcileGCRollout()
    job.user.is_superuser = True
    modules.jobs.JobResult.objects.get.return_value.status = "STARTED"
    with pytest.raises(ValueError, match="still active"): job.run("run", "review")
    assert ledger["stage"] == "needs_reconciliation"

@pytest.fixture
def current_manifest(modules, prepared):
    m = modules.manifest
    manifest = m.build("user", prepared[0])
    m.GitRepository.objects.get.return_value = m.GitRepository.objects.restrict.return_value.get.return_value
    by_id = {str(p.pk): p for p in prepared[1]}
    m.ConfigPlan.objects.select_related.return_value.get.side_effect = lambda pk: by_id[pk]
    return manifest, by_id


def test_validate_unchanged_plans(modules, current_manifest):
    manifest, _ = current_manifest
    modules.manifest.validate_current(manifest, [p["device"] for p in manifest["plans"]])


@pytest.mark.parametrize("field,value", [("config_set", "no ntp server 192.168.3.242"),
    ("deploy_result_id", "someone-else"), ("change_control_id", "different"), ("plan_result_id", "regenerated")])
def test_actual_revalidation_rejects_plan_changes(modules, current_manifest, field, value):
    manifest, plans = current_manifest
    setattr(plans["plan-1"], field, value)
    with pytest.raises(ValueError, match="changed|used"):
        modules.manifest.validate_current(manifest, ["CE1"])


def test_revalidation_rejects_intended_change_even_after_wave(modules, current_manifest):
    manifest, _ = current_manifest
    modules.manifest.GoldenConfig.objects.get.return_value.intended_config = "ntp server 192.0.2.99"
    with pytest.raises(ValueError, match="Intended config changed"):
        modules.manifest.validate_current(manifest, [])


def test_revalidation_rejects_source_change(modules, current_manifest):
    manifest, _ = current_manifest
    modules.manifest.GitRepository.objects.get.return_value.current_head = "b"*40
    with pytest.raises(ValueError, match="Source HEAD changed"):
        modules.manifest.validate_current(manifest, ["CE1"])


def test_revalidation_rejects_rule_change(modules, current_manifest, monkeypatch):
    manifest, _ = current_manifest
    monkeypatch.setattr(modules.manifest, "rules_snapshot", lambda *args: [])
    with pytest.raises(ValueError, match="rules changed"):
        modules.manifest.validate_current(manifest, ["CE1"])


def test_preparation_performs_no_deploy(modules, prepared, monkeypatch):
    monkeypatch.setattr(modules.jobs, "deploy", Mock(side_effect=AssertionError("must not deploy")))
    result = modules.jobs.PrepareGCRollout().run(json.dumps(prepared[0]))
    assert result["stage"] == "prepared" and not result["execution_job"]
    assert result["claimed_plans"] == []
    modules.jobs.deploy.assert_not_called()


def test_existing_unreconciled_run_blocks_new_run(modules, execution):
    job, ledger, calls = execution
    modules.jobs.JobResult.objects.filter.return_value.exclude.return_value.iterator.return_value = iter([
        types.SimpleNamespace(pk="old", result={"execution_job": "old-exec", "stage": "needs_reconciliation"})])
    with pytest.raises(ValueError, match="reconciliation"):
        job.run("run", ledger["approval_digest"], "approved")
    assert calls == []


def test_cancel_wrong_user_rejected(modules, execution):
    _, ledger, _ = execution
    modules.jobs.JobResult.objects.get.return_value.user_id = "different-user"
    with pytest.raises(PermissionError): modules.jobs.CancelGCRollout().run("run", "stop")
    assert not ledger["cancel_requested"]


def test_reconcile_never_clears_claims(modules, execution):
    _, ledger, _ = execution
    ledger.update(stage="needs_reconciliation", execution_job="old", claimed_plans=["p1"])
    job = modules.jobs.ReconcileGCRollout()
    job.user.is_superuser = True
    modules.jobs.JobResult.objects.get.return_value.status = "FAILURE"
    job.run("run", "reviewed live devices")
    assert ledger["claimed_plans"] == ["p1"] and ledger["stage"] == "reconciled"


@pytest.fixture
def source_repo(modules, tmp_path):
    import subprocess
    root = tmp_path / "repo"
    root.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    git("init", "-q")
    git("config", "user.name", "Rollout Test")
    git("config", "user.email", "rollout-test@example.invalid")
    (root / "jobs").mkdir()
    (root / "jobs/job.py").write_text("# original source\n")
    (root / "backups").mkdir()
    (root / "backups/CE1.cfg").write_text("old config\n")
    git("add", ".")
    git("commit", "-qm", "baseline")
    head = git("rev-parse", "HEAD")
    repo = types.SimpleNamespace(pk="repo", name="blog-sandbox", current_head=head, filesystem_path=str(root))
    approved = {"id": "repo", "name": "blog-sandbox", "commit": head, "backup_paths": ["backups/CE1.cfg"]}
    return modules.jobs.source if hasattr(modules.jobs, "source") else sys.modules["rollout_under_test.source"], root, repo, approved, git


def test_source_accepts_only_reviewed_backup_commit(source_repo):
    source, root, repo, approved, git = source_repo
    (root / "backups/CE1.cfg").write_text("new config\n")
    git("add", ".")
    git("commit", "-qm", "backup evidence")
    repo.current_head = git("rev-parse", "HEAD")
    source.validate_source(repo, approved)


@pytest.mark.parametrize("filename", ["jobs/job.py", "backups/other.cfg"])
def test_source_rejects_unapproved_commit(source_repo, filename):
    source, root, repo, approved, git = source_repo
    (root / filename).write_text("changed\n")
    git("add", ".")
    git("commit", "-qm", "unapproved")
    repo.current_head = git("rev-parse", "HEAD")
    with pytest.raises(ValueError, match="outside approved"):
        source.validate_source(repo, approved)


def test_source_rejects_dirty_worktree(source_repo):
    source, root, repo, approved, _ = source_repo
    (root / "jobs/job.py").write_text("dirty\n")
    with pytest.raises(ValueError, match="Uncommitted"):
        source.validate_source(repo, approved)


def test_source_checks_checkout_even_if_database_head_stale(source_repo):
    source, root, repo, approved, git = source_repo
    (root / "jobs/job.py").write_text("changed\n")
    git("add", ".")
    git("commit", "-qm", "unapproved")
    with pytest.raises(ValueError, match="outside approved"):
        source.validate_source(repo, approved)


@pytest.mark.parametrize("path", ["../jobs.py", "/etc/config", "jobs/config.py", ".git/config", ".", "__init__.py", "requirements.txt"])
def test_invalid_backup_paths(modules, path):
    source = sys.modules["rollout_under_test.source"]
    with pytest.raises(ValueError): source.relative_backup_path(path)


def test_actual_iosxe_driver_name_is_supported(modules, prepared):
    for p in prepared[1][:2]:
        p.device.platform.network_driver = "cisco_ios"
    result = modules.manifest.build("user", prepared[0])
    assert any(p["platform"] == "cisco_ios" for p in result["plans"])


def test_verification_uses_nautobot_inventory_credentials_and_driver(modules, monkeypatch):
    verify = modules.verify
    monkeypatch.setattr(verify, "check_cancel", lambda _: None)
    settings = {"credentials": "site.credentials.NautobotDeviceCredentials",
                "inventory_params": {"use_fqdn": False}}
    monkeypatch.setattr(verify, "NORNIR_SETTINGS", settings)
    connection = Mock()
    connection.check_enable_mode.return_value = True
    connection.send_command.return_value = "ntp server 192.0.2.1"
    options = types.SimpleNamespace(platform="driver-from-nautobot", username="inventory-user",
                                    password="inventory-test-value", extras={"secret": "inventory-test-secret"})
    host = Mock()
    host.connection_options = {"netmiko": options}
    host.get_connection.return_value = connection
    nr = types.SimpleNamespace(inventory=types.SimpleNamespace(hosts={"CE1": host}), config=object())
    initialize = Mock(return_value=nullcontext(nr))
    monkeypatch.setattr(verify, "InitNornir", initialize)
    manifest = {"plans": [{"device": "CE1", "device_id": "device1", "baseline_ntp": ["ntp server 192.0.2.1"]}], "spec": {}}
    assert verify.verify_wave(Mock(), "run", manifest, ["CE1"], baseline=True)[0]["baseline_matches"]
    inventory = initialize.call_args.kwargs["inventory"]
    assert inventory["plugin"] == "nautobot-inventory"
    assert inventory["options"]["credentials_class"] == settings["credentials"]
    assert inventory["options"]["params"] == settings["inventory_params"]
    assert options.platform == "driver-from-nautobot"
    assert options.username == "inventory-user" and options.password == "inventory-test-value"
    assert options.extras["secret"] == "inventory-test-secret"
    host.get_connection.assert_called_once_with("netmiko", nr.config)


def test_manifest_contains_no_credentials(modules, prepared):
    manifest = modules.manifest.build("user", prepared[0])
    def check(value):
        if isinstance(value, dict):
            assert not {"username", "password", "secret", "credentials"} & set(value)
            for item in value.values(): check(item)
        elif isinstance(value, list):
            for item in value: check(item)
    check(manifest)


def test_builtin_postprocessing_supported_and_bound(modules, prepared, monkeypatch):
    m = modules.manifest
    builtin = "nautobot_golden_config.utilities.config_postprocessing.render_secrets"
    monkeypatch.setattr(m, "ENABLE_POSTPROCESSING", True)
    monkeypatch.setattr(m, "PLUGIN_CFG", {"postprocessing_callables": [builtin], "postprocessing_subscribed": []})
    checks = Mock()
    monkeypatch.setattr(m, "verify_postprocessing", checks)
    manifest = m.build("user", prepared[0])
    assert manifest["postprocessing"] == {"enabled": True, "callables": [builtin, builtin]}
    assert checks.call_count == len(prepared[1])


def test_custom_postprocessing_refused(modules, monkeypatch):
    m = modules.manifest
    monkeypatch.setattr(m, "ENABLE_POSTPROCESSING", True)
    monkeypatch.setattr(m, "PLUGIN_CFG", {"postprocessing_callables": ["custom.change_commands"]})
    with pytest.raises(ValueError, match="custom postprocessing"):
        m.postprocessing_snapshot()


def test_postprocessing_change_invalidates_approval(modules, current_manifest, monkeypatch):
    manifest, _ = current_manifest
    monkeypatch.setattr(modules.manifest, "ENABLE_POSTPROCESSING", True)
    monkeypatch.setattr(modules.manifest, "PLUGIN_CFG", {})
    with pytest.raises(ValueError, match="Postprocessing changed"):
        modules.manifest.validate_current(manifest, ["CE1"])


@pytest.mark.parametrize("marker", ["{{ value }}", "{% do_something %}", "{# hidden #}"])
def test_unresolved_templates_refused(modules, prepared, marker):
    prepared[1][0].config_set = "ntp server " + marker
    with pytest.raises(ValueError, match="literal plan"):
        modules.manifest.build("user", prepared[0])


@pytest.mark.parametrize("rendered,accepted", [("ntp server 192.0.2.1\n", True), ("ntp server 192.0.2.99", False)])
def test_rendered_commands_must_match_reviewed_text(modules, monkeypatch, rendered, accepted):
    http = types.ModuleType("django.http")
    http.HttpRequest = types.SimpleNamespace
    monkeypatch.setitem(sys.modules, "django.http", http)
    renderer = types.ModuleType("nautobot_golden_config.utilities.config_postprocessing")
    renderer.get_config_postprocessing = Mock(return_value=rendered)
    monkeypatch.setitem(sys.modules, renderer.__name__, renderer)
    plan = types.SimpleNamespace(pk="plan", config_set="ntp server 192.0.2.1")
    if accepted:
        modules.manifest.verify_postprocessing(plan, "user", {"enabled": True})
    else:
        with pytest.raises(ValueError, match="changed the reviewed commands"):
            modules.manifest.verify_postprocessing(plan, "user", {"enabled": True})
