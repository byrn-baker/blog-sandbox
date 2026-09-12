"""Migrate the lab server IPv4 addresses while retaining interface bindings."""

from django.db import transaction
from nautobot.apps.jobs import BooleanVar, Job, register_jobs
from nautobot.ipam.models import IPAddress, Prefix

from ..sp_demo_lab.context import SPDemoLabContext


class LabServerAddressing(Job):
    dry_run = BooleanVar(default=True)

    class Meta:
        name = "Lab Server Addressing"
        description = "Move the modeled VLAN 100 addresses to the Git-defined server subnet."

    def run(self, dry_run):
        subnet = next(v for v in SPDemoLabContext.service_vlans if v["id"] == 100)
        expected = {s["host_octet"]: {(s["name"], "bond0")} for s in SPDemoLabContext.servers}
        network = SPDemoLabContext.dc_a_devices + SPDemoLabContext.dc_b_devices + SPDemoLabContext.dc_c_devices
        expected[1] = {(d["name"], "Vlan100") for d in network if d["role"] == "Leaf"}
        with transaction.atomic():
            old = Prefix.objects.get(prefix="192.168.100.0/24", namespace__name="Global")
            target, created = Prefix.objects.get_or_create(
                prefix=subnet["ipv4_prefix"], namespace=old.namespace,
                defaults={"status": old.status, "type": old.type, "description": "VLAN 100 server network"},
            )
            if created:
                target.locations.set(old.locations.all())
                target.vrfs.set(old.vrfs.all())
                target.vlan = old.vlan
                target.validated_save()
            rows = list(IPAddress.objects.filter(parent__in=[old, target]).prefetch_related("interfaces__device"))
            if len(rows) != len(expected):
                raise ValueError("Unexpected address count in the old or new server prefix")
            seen = set()
            changes = []
            base = subnet["ipv4_prefix"].rsplit(".", 1)[0]
            for address in rows:
                octet = int(str(address.host).rsplit(".", 1)[1])
                bindings = {(i.device.name, i.name) for i in address.interfaces.all()}
                if octet in seen or bindings != expected.get(octet):
                    raise ValueError(f"Unexpected interface bindings for {address.address}: {bindings}")
                seen.add(octet)
                desired = f"{base}.{octet}/24"
                if str(address.address) != desired:
                    changes.append((str(address.address), desired))
                    replacement = IPAddress(
                        address=desired, parent=target, status=address.status,
                        type=address.type, description=address.description,
                    )
                    replacement.validated_save()
                    for interface in address.interfaces.all():
                        interface.ip_addresses.add(replacement)
                        interface.ip_addresses.remove(address)
                    address.delete()
            if seen != set(expected):
                raise ValueError("Incomplete server addressing inventory")
            for before, after in changes:
                self.logger.info("%s -> %s", before, after)
            if dry_run:
                transaction.set_rollback(True)
            return {"dry_run": dry_run, "changes": changes}


register_jobs(LabServerAddressing)
