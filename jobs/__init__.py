from nautobot.apps.jobs import register_jobs

from .gc_bootstrap import GCBootstrap
from .gc_compliance_setup import GCComplianceSetup
from .sp_demo_lab import SPDemoLabDesign

register_jobs(GCBootstrap, GCComplianceSetup, SPDemoLabDesign)
