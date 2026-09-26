"""Reserve the Git-defined NTP service addresses in Nautobot IPAM."""
from pathlib import Path

import yaml
from django.db import transaction
from nautobot.apps.jobs import BooleanVar, Job, register_jobs
from nautobot.extras.models import Status
from nautobot.ipam.models import IPAddress, Prefix


class NTPReservations(Job):
    dry_run = BooleanVar(default=True)

    class Meta:
        name = "NTP VIP Reservations"
        description = "Reserve the management and lab MetalLB NTP IPs in Global IPAM."

    def run(self, dry_run):
        data = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "service_endpoints.yml").read_text()
        )
        status = Status.objects.get(name="Reserved")
        addresses = []
        with transaction.atomic():
            for kind in ("management", "lab"):
                host = data[f"ntp_{kind}_ip"]
                prefix = Prefix.objects.get(
                    prefix=host.rsplit(".", 1)[0] + ".0/24",
                    namespace__name="Global",
                )
                description = f"Git-managed MetalLB NTP ({kind})"
                existing = IPAddress.objects.filter(parent=prefix, host=host).first()
                if existing and (
                    existing.description != description or existing.interfaces.exists()
                ):
                    raise ValueError(f"Refusing to claim an existing address: {host}")
                obj = existing or IPAddress(address=host + "/24", parent=prefix)
                obj.status = status
                obj.description = description
                obj.validated_save()
                addresses.append(host)
                self.logger.info("Reserved %s", host)
            if dry_run:
                transaction.set_rollback(True)
        return {"dry_run": dry_run, "addresses": addresses}


register_jobs(NTPReservations)
