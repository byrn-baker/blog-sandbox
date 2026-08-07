"""SP Demo Lab — Design Builder job for the full lab topology."""

from nautobot.apps.jobs import register_jobs
from nautobot_design_builder.choices import DesignModeChoices
from nautobot_design_builder.design_job import DesignJob

from .context import SPDemoLabContext


class SPDemoLabDesign(DesignJob):
    """Populate the SP demo lab: 28 devices, interfaces, IPs, VRFs, cabling."""

    class Meta:
        name = "SP Demo Lab - Full Topology"
        description = (
            "Greenfield: 13 Cisco CAT8000v (IOS-XE) + 15 Arista vEOS across "
            "an MPLS SP core and 3 DC leaf-spine fabrics. Creates devices, "
            "interfaces, management IPs, loopbacks, P2P /31 links, VRFs, "
            "prefixes, and cables."
        )
        design_mode = DesignModeChoices.DEPLOYMENT
        commit_default = True
        context_class = SPDemoLabContext
        design_files = [
            "designs/0001_foundations.yaml.j2",
            "designs/0002_devices.yaml.j2",
            "designs/0003_cabling.yaml.j2",
            "designs/0004_routing.yaml.j2",
        ]
        version = "1.0.0"
        has_sensitive_variables = False


name = "SP Demo Lab"
register_jobs(SPDemoLabDesign)
