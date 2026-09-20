"""Reserve the Git-defined telemetry endpoint before device export."""
from pathlib import Path

import yaml
from django.db import transaction
from nautobot.apps.jobs import BooleanVar, Job, register_jobs
from nautobot.extras.models import Status
from nautobot.ipam.models import IPAddress, Prefix


class TelemetryReservation(Job):
    dry_run = BooleanVar(default=True)

    class Meta:
        name = "Telemetry VIP Reservation"
        description = "Reserve the Git-defined Part 8 telemetry VIP."

    def run(self, dry_run):
        data = yaml.safe_load((Path(__file__).resolve().parents[2] / "service_endpoints.yml").read_text())
        host = data["telemetry_ip"]
        description = "Git-managed MetalLB telemetry"
        with transaction.atomic():
            prefix = Prefix.objects.get(prefix=host.rsplit('.', 1)[0] + '.0/24', namespace__name="Global")
            existing = IPAddress.objects.filter(parent=prefix, host=host).first()
            if existing and (existing.description != description or existing.interfaces.exists()):
                raise ValueError("Telemetry address already has another owner")
            obj = existing or IPAddress(address=host + '/24', parent=prefix)
            obj.status = Status.objects.get(name="Reserved")
            obj.description = description
            obj.validated_save()
            if dry_run:
                transaction.set_rollback(True)
        self.logger.info("Telemetry VIP %s, dry_run=%s", host, dry_run)
        return {"address": host, "dry_run": dry_run}


register_jobs(TelemetryReservation)
