"""Migrate only modeled lab interface MTUs; never connect to devices."""

from django.db import transaction
from nautobot.apps.jobs import BooleanVar, Job, register_jobs
from nautobot.dcim.models import Device, Interface

from ..sp_demo_lab.context import SPDemoLabContext


def target_mtu(platform, name, mgmt_only=False, vrf="", role="", server=False):
    """Return the managed MTU, or None for interfaces outside this policy."""
    policy = SPDemoLabContext.mtu_policy
    if mgmt_only or vrf == "MGMT-VRF" or role == "NAT Outside":
        return None
    if platform == "cisco_iosxe" and name.startswith("GigabitEthernet") and name != "GigabitEthernet1":
        return policy["router"]
    if platform == "arista_eos":
        if name.startswith("Ethernet"):
            return policy["fabric"]
        # Only modeled service gateways, not the dynamic L3-VNI interface.
        if name in {f"Vlan{v['id']}" for v in SPDemoLabContext.service_vlans}:
            return policy["server"]
    if server and name in {"bond0", "ens19", "ens20"}:
        return policy["server"]
    return None


class StandardLabMTU(Job):
    """Update existing lab MTU fields without rerunning the full topology design."""

    dry_run = BooleanVar(default=True, description="Preview only; leave modeled interfaces unchanged.")

    class Meta:
        name = "Standard Lab MTU"
        description = "Preview or apply the standard jumbo MTUs to existing lab interface records."

    def run(self, dry_run):
        context = SPDemoLabContext
        network = context.sp_core_devices + context.dc_a_devices + context.dc_b_devices + context.dc_c_devices
        servers = {s["name"] for s in context.servers}
        expected = {d["name"] for d in network} | servers
        with transaction.atomic():
            devices = list(Device.objects.filter(name__in=expected).select_related("platform"))
            if {d.name for d in devices} != expected:
                raise ValueError("The complete modeled lab inventory is required before MTU migration.")
            changes = []
            for device in devices:
                platform = device.platform.name if device.platform else ""
                for interface in Interface.objects.select_for_update(of=("self",)).filter(device=device).select_related("vrf", "role"):
                    mtu = target_mtu(
                        platform, interface.name, interface.mgmt_only,
                        interface.vrf.name if interface.vrf else "",
                        interface.role.name if interface.role else "",
                        device.name in servers,
                    )
                    if mtu is None or interface.mtu == mtu:
                        continue
                    changes.append({"device": device.name, "interface": interface.name, "before": interface.mtu, "after": mtu})
                    if not dry_run:
                        interface.mtu = mtu
                        interface.validated_save()
            for change in changes:
                self.logger.info("%s %s MTU %s -> %s", change["device"], change["interface"], change["before"], change["after"])
            return {"dry_run": dry_run, "count": len(changes), "changes": changes}


register_jobs(StandardLabMTU)
