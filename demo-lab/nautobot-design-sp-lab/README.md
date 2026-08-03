# SP Demo Lab — Nautobot Design Builder Job

Drop this folder into `nautobot-docker-compose/jobs/` and restart Nautobot.
The design job appears in Jobs UI under "SP Demo Lab".

## Usage

```bash
# Copy into your nautobot-docker-compose jobs folder
cp -r sp_demo_lab ~/nautobot-docker-compose/jobs/

# Rebuild & restart (picks up new jobs)
cd ~/nautobot-docker-compose
invoke stop start
```

Then: **Jobs → SP Demo Lab - Full Topology → Run**

## Prerequisites

`nautobot-design-builder` must be installed in Nautobot:
```bash
cd ~/nautobot-docker-compose
poetry add nautobot-design-builder
invoke build --no-cache
invoke stop start
```

And enabled in `config/nautobot_config.py`:
```python
PLUGINS = ["nautobot_design_builder"]
```

## What it creates

28 devices (13 Cisco CAT8000v + 15 Arista vEOS), full IPAM, cabling, VRFs.
See context.py for the complete data set.

## File layout

```
jobs/
  sp_demo_lab/
    __init__.py          # DesignJob class + register_jobs()
    context/
      __init__.py        # Context class (provides data to templates)
    designs/
      0001_foundations.yaml.j2  # locations, roles, platforms, device types
      0002_devices.yaml.j2      # all 28 devices with interfaces + IPs
      0003_cabling.yaml.j2      # inter-device cables + P2P IPs
```
