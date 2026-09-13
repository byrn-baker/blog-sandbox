"""Grafana dashboard definition generated alongside the Nautobot fleet."""


def dashboard(expected_devices):
    ds = {"type": "prometheus", "uid": "network-snmp"}
    selected = '{job="snmp",if_type!="",if_type!="166",interface!~"(VoIP-)?Null0",device=~"$device",interface=~"$interface"}'
    panels = []

    def panel(title, expression, unit, kind="timeseries", description=""):
        i = len(panels)
        panels.append({"id": i + 1, "title": title, "type": kind, "datasource": ds,
            "description": description, "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8},
            "targets": [{"refId": "A", "expr": expression, "instant": kind in ["stat", "table"], "format": "table" if kind == "table" else "time_series"}],
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull"]}}})
        target = panels[-1]["targets"][0]
        if kind == "timeseries":
            target["legendFormat"] = "{{device}} / {{interface}}" if "snmp_interface_" in expression else "{{device}}"
        if kind == "table":
            names = ["device", "interface", "Value"] if "snmp_interface_" in expression else ["device", "Value"]
            panels[-1]["transformations"] = [
                {"id": "filterFieldsByName", "options": {"include": {"names": names}}},
                {"id": "organize", "options": {"indexByName": {n: i for i, n in enumerate(names)},
                    "renameByName": {"device": "Device", "interface": "Interface", "Value": title}}}]
            panels[-1]["options"] = {"showHeader": True, "sortBy": [{"displayName": "Device", "desc": False}]}

    panel("Devices polled in the last 3 minutes (expected " + str(expected_devices) + ")",
          'count(max by (device) (timestamp(snmp_device_uptime_ticks{job="snmp"})) > time() - 180) or vector(0)', "short", "stat")
    panel("Device uptime", 'snmp_device_uptime_ticks{job="snmp",device=~"$device"} / 100', "s", "table",
          "SNMP sysUpTime is hundredths of a second and wraps after about 497 days.")
    panel("Inbound traffic", "rate(snmp_interface_in_octets_total" + selected + "[5m]) * 8", "bps")
    panel("Outbound traffic", "rate(snmp_interface_out_octets_total" + selected + "[5m]) * 8", "bps")
    panel("Inbound utilization", "100 * rate(snmp_interface_in_octets_total" + selected +
          "[5m]) * 8 / (snmp_interface_speed_mbps" + selected + " * 1000000 > 0)", "percent",
          description="Uses reported interface speed. Virtual interface speed is not a measured forwarding capacity.")
    panel("Outbound utilization", "100 * rate(snmp_interface_out_octets_total" + selected +
          "[5m]) * 8 / (snmp_interface_speed_mbps" + selected + " * 1000000 > 0)", "percent")
    panel("Inbound errors", "rate(snmp_interface_in_errors_total" + selected + "[5m])", "ops")
    panel("Outbound errors", "rate(snmp_interface_out_errors_total" + selected + "[5m])", "ops")
    panel("Inbound discards", "rate(snmp_interface_in_discards_total" + selected + "[5m])", "ops")
    panel("Outbound discards", "rate(snmp_interface_out_discards_total" + selected + "[5m])", "ops")
    panel("Interface status", "snmp_interface_oper_status" + selected, "none", "table",
          "Names match the full CLI interface names. MPLS protocol-layer rows and IOS null sinks are excluded from normal interface views. Arista internal Vlan4097 is absent from the collected IF-MIB rows.")
    panel("Sample age", 'time() - timestamp(snmp_device_uptime_ticks{job="snmp",device=~"$device"})', "s", "table",
          "Missing samples are unknown, not zero traffic. Devices missing over the query lookback disappear; compare fleet count above.")
    # Keep unsupported MPLS-layer counters visible as a diagnostic, not as duplicate physical links.
    panel("MPLS pseudo-interfaces without error counters",
          'snmp_interface_oper_status{job="snmp",if_type="166",device=~"$device"}' +
          ' unless on(device,if_index) snmp_interface_in_errors_total{job="snmp",if_type!=""}', "none", "table",
          "These are SNMP protocol-layer rows, not additional CLI interfaces. They can duplicate physical-link traffic. Missing error/discard counters mean unsupported, not zero. This diagnostic follows Device selection only.")
    panels[-1]["transformations"][0]["options"]["include"]["names"] = ["device", "interface"]
    panels[-1]["transformations"][1]["options"]["renameByName"]["interface"] = "SNMP protocol-layer row"
    panel("Polling errors in the last 5 minutes",
          'label_replace(sum by (receiver) (increase(otelcol_scraper_errored_metric_points{receiver=~"snmp/($device)"}[5m])), "device", "$1", "receiver", "snmp/(.*)")', "short")
    panels[-1]["datasource"] = {"uid": "VictoriaMetrics"}
    panel("Queued export requests", 'max by (exporter) (otelcol_exporter_queue_size{exporter=~"otlp_http/(snmp_history|victoriametrics)"})', "short")
    panels[-1]["datasource"] = {"uid": "VictoriaMetrics"}
    panel("Metric points exported per second",
          'sum by (exporter) (rate(otelcol_exporter_sent_metric_points{exporter=~"otlp_http/(snmp_history|victoriametrics)"}[5m]))', "ops")
    panels[-1]["datasource"] = {"uid": "VictoriaMetrics"}
    for item in panels:
        if item["title"] in ["Queued export requests", "Metric points exported per second"]:
            target = item["targets"][0]
            target["expr"] = ('label_replace(label_replace(' + target["expr"] +
                ', "destination", "SNMP history", "exporter", "otlp_http/snmp_history"), ' +
                '"destination", "Cluster metrics", "exporter", "otlp_http/victoriametrics")')
            target["legendFormat"] = "{{destination}}"
        if item["title"] == "Interface status":
            item["fieldConfig"]["defaults"]["mappings"] = [{"type": "value", "options": {
                str(value): {"text": text, "color": color}
                for value, text, color in [(1, "Up", "green"), (2, "Down", "red"),
                    (3, "Testing", "yellow"), (4, "Unknown", "gray"), (5, "Dormant", "yellow"),
                    (6, "Not present", "gray"), (7, "Lower layer down", "red")]}}]
        if item["title"] in ["Inbound errors", "Outbound errors"]:
            item["fieldConfig"]["defaults"]["unit"] = "suffix: errors/s"
        if item["title"] in ["Inbound discards", "Outbound discards"]:
            item["fieldConfig"]["defaults"]["unit"] = "suffix: discards/s"
        if item["title"] == "Metric points exported per second":
            item["fieldConfig"]["defaults"]["unit"] = "suffix: points/s"
    return {"uid": "network-snmp", "title": "Network SNMP", "tags": ["network", "snmp"],
            "schemaVersion": 39, "version": 2, "editable": False, "timezone": "browser",
            "refresh": "30s", "time": {"from": "now-1h", "to": "now"}, "panels": panels,
            "templating": {"list": [
                {"name": "device", "label": "Device", "type": "query", "datasource": ds,
                 "query": "label_values(snmp_device_uptime_ticks, device)", "refresh": 1,
                 "multi": True, "includeAll": True, "allValue": ".*", "current": {"text": "All", "value": "$__all"}},
                {"name": "interface", "label": "Interface", "type": "query", "datasource": ds,
                 "query": 'label_values(snmp_interface_oper_status{job="snmp",if_type!="",if_type!="166",interface!~"(VoIP-)?Null0",device=~"$device"}, interface)', "refresh": 1,
                 "multi": True, "includeAll": True, "allValue": ".*", "current": {"text": "All", "value": "$__all"}}
            ]}}
