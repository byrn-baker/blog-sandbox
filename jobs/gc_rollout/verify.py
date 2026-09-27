"""Read-only, bounded NTP verification using Golden Config's inventory credentials."""
import re
import time
from threading import Event
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import close_old_connections
from nautobot.dcim.models import Device
from nautobot_plugin_nornir.constants import NORNIR_SETTINGS
from nornir import InitNornir
# Import registers the same ORM inventory plugin as Golden Config.
from nautobot_golden_config.nornir_plays import config_deployment as _deployment

from . import state
from .manifest import ntp_lines


class RolloutCanceled(RuntimeError):
    """Cooperative stop; already deployed changes are not reverted."""


def check_cancel(run_id):
    if state.canceled(run_id):
        raise RolloutCanceled("Cancellation requested; no further rollout stages will start")


def peer_state(status, associations, server):
    responding = selected = False
    for line in associations.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] in {"*", "+", "-", "~", "#"} and len(fields) > 1:
            fields = [fields[0] + fields[1], *fields[2:]]
        if fields[0].lstrip("*+~-#ox.") != server or len(fields) < 8:
            continue
        try:
            responding |= int(fields[-4], 8) > 0
        except ValueError:
            pass
        selected |= "*" in fields[0]
    synchronized = bool(re.search(r"clock is synchroni[sz]ed|synchroni[sz]ed to NTP server", status, re.I))
    synchronized &= not bool(re.search(r"not synchroni[sz]ed|unsynchroni[sz]ed", status, re.I))
    return responding, bool(synchronized and selected and responding)


def command(connection, text):
    output = connection.send_command(text, read_timeout=45)
    if re.search(r"%\s*(Invalid|Error|Incomplete|Ambiguous)|Invalid input", output, re.I):
        raise ValueError(f"Verification command rejected: {text}")
    return output


def verify_wave(job, run_id, manifest, names, baseline=False):
    entries = {p["device"]: p for p in manifest["plans"] if p["device"] in names}
    spec = manifest["spec"]
    check_cancel(run_id)
    device_qs = Device.objects.filter(pk__in=[p["device_id"] for p in entries.values()])
    stop = Event()
    with InitNornir(
        logging={"enabled": False},
        inventory={"plugin": "nautobot-inventory", "options": {
            "credentials_class": NORNIR_SETTINGS.get("credentials"),
            "params": NORNIR_SETTINGS.get("inventory_params"), "queryset": device_qs,
        }},
    ) as nr:
        if set(nr.inventory.hosts) != set(names):
            raise ValueError("Verification inventory does not match the approved devices")

        def observe(name):
            close_old_connections()
            host = nr.inventory.hosts[name]
            entry = entries[name]
            try:
                check_cancel(run_id)
                if stop.is_set():
                    raise RuntimeError("Another device failed verification")
                # Bound SSH setup, preserving inventory connection credentials/options.
                options = host.connection_options["netmiko"]
                options.extras = {**(options.extras or {}), "conn_timeout": 30, "auth_timeout": 30, "banner_timeout": 30}
                conn = host.get_connection("netmiko", nr.config)
                if not conn.check_enable_mode():
                    conn.enable()
                running = ntp_lines(command(conn, "show running-config | include ^ntp"))
                if baseline:
                    if running != entry["baseline_ntp"]:
                        raise ValueError(f"{name}: running NTP differs from the reviewed backup; regenerate plans")
                    return {"device": name, "baseline_matches": True}
                startup = ntp_lines(command(conn, "show startup-config | include ^ntp"))
                sample = {"applied": running == entry["expected_ntp"],
                          "saved": startup == entry["expected_ntp"], "peer_responding": False,
                          "synchronized": False, "stage": "applied", "running_ntp": running, "startup_ntp": startup}
                if not sample["applied"] or not sample["saved"]:
                    sample["stage"] = "verification_failed"
                    state.progress(run_id, name, sample)
                    raise ValueError(f"{name}: intended NTP must match both running and startup config")
                sample["stage"] = "saved"
                state.progress(run_id, name, sample)
                job.logger.info("%s: applied and saved; waiting for NTP peer/synchronization", name)
                deadline = time.monotonic() + spec["timeout_seconds"]
                previous = "saved"
                while True:
                    check_cancel(run_id)
                    if stop.is_set():
                        raise RuntimeError("Another device failed verification")
                    status = command(conn, "show ntp status")
                    associations = command(conn, "show ntp associations")
                    responding, synced = peer_state(status, associations, spec["ntp_server"])
                    sample.update({"peer_responding": responding, "synchronized": synced,
                                   "stage": "synchronized" if synced else "peer_responding" if responding else "saved",
                                   "ntp_status": status, "ntp_associations": associations})
                    state.progress(run_id, name, sample)
                    if previous != sample["stage"]:
                        job.logger.info("%s: %s", name, sample["stage"])
                        previous = sample["stage"]
                    if synced:
                        return {"device": name, "synchronized": True}
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"{name}: NTP did not synchronize within the approved timeout")
                    # Short sleeps let cooperative cancellation interrupt acquisition waits.
                    end = min(deadline, time.monotonic() + spec["poll_seconds"])
                    while time.monotonic() < end:
                        check_cancel(run_id)
                        time.sleep(min(1, max(0, end - time.monotonic())))
            except Exception as exc:
                stop.set()
                job.logger.error("%s verification stopped: %s", name, str(exc))
                state.progress(run_id, name, {"stage": "canceled" if isinstance(exc, RolloutCanceled) else "verification_failed",
                                              "error_type": type(exc).__name__})
                raise
            finally:
                host.close_connections()
                close_old_connections()

        results, errors = [], []
        # A wave bounds deployment concurrency; verification uses at most eight SSH sessions.
        with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
            futures = {pool.submit(observe, name): name for name in names}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    errors.append((futures[future], exc))
        if errors:
            if any(isinstance(exc, RolloutCanceled) for _, exc in errors):
                raise RolloutCanceled("Cancellation requested during verification")
            raise RuntimeError("Verification failed for " + ", ".join(f"{n} ({type(e).__name__})" for n, e in errors))
        return results
