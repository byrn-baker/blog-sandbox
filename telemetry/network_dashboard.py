"""Grafana dashboard definition generated alongside the Nautobot fleet."""


def dashboard(expected_devices):
    ds = {"type": "prometheus", "uid": "network-snmp"}
    selected = '{job="snmp",if_type!="",device=~"$device",interface=~"$interface"}'
    panels = []

    def panel(title, expression, unit, kind="timeseries", description=""):
        i = len(panels)
        panels.append({"id": i + 1, "title": title, "type": kind, "datasource": ds,
            "description": description, "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8},
            "targets": [{"refId": "A", "expr": expression, "instant": kind in ["stat", "table"], "format": "table" if kind == "table" else "time_series"}],
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []}, "options": {}})

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
    panel("Interface operational state", "snmp_interface_oper_status" + selected, "short", "table",
          "IF-MIB: 1 up, 2 down, 3 testing, 4 unknown, 5 dormant, 6 notPresent, 7 lowerLayerDown.")
    panel("Sample age", 'time() - timestamp(snmp_device_uptime_ticks{job="snmp",device=~"$device"})', "s", "table",
          "Missing samples are unknown, not zero traffic. Devices missing over the query lookback disappear; compare fleet count above.")
    panel("Interface rows without error counters", "snmp_interface_oper_status" + selected +
          ' unless on(device,if_index) snmp_interface_in_errors_total{job="snmp",if_type!=""}', "short", "table",
          "IOS MPLS-layer rows return NoSuchInstance for error/discard counters. They are separate from the physical interface. Missing is not zero; the physical interface has its own counters.")
    panel("Polling errors in the last 5 minutes",
          'sum by (receiver) (increase(otelcol_scraper_errored_metric_points{receiver=~"snmp/.*"}[5m]))', "short")
    panels[-1]["datasource"] = {"uid": "VictoriaMetrics"}
    panel("Queued export requests", 'max by (exporter) (otelcol_exporter_queue_size{exporter=~"otlp_http/(snmp_history|victoriametrics)"})', "short")
    panels[-1]["datasource"] = {"uid": "VictoriaMetrics"}
    panel("Metric points exported per second",
          'sum by (exporter) (rate(otelcol_exporter_sent_metric_points{exporter=~"otlp_http/(snmp_history|victoriametrics)"}[5m]))', "ops")
    panels[-1]["datasource"] = {"uid": "VictoriaMetrics"}
    return {"uid": "network-snmp", "title": "Network SNMP", "tags": ["network", "snmp"],
            "schemaVersion": 39, "version": 1, "editable": False, "timezone": "browser",
            "refresh": "30s", "time": {"from": "now-1h", "to": "now"}, "panels": panels,
            "templating": {"list": [
                {"name": "device", "type": "query", "datasource": ds,
                 "query": "label_values(snmp_device_uptime_ticks, device)", "refresh": 1,
                 "multi": True, "includeAll": True, "allValue": ".*", "current": {"text": "All", "value": "$__all"}},
                {"name": "interface", "type": "query", "datasource": ds,
                 "query": 'label_values(snmp_interface_oper_status{job="snmp",if_type!="",device=~"$device"}, interface)', "refresh": 1,
                 "multi": True, "includeAll": True, "allValue": ".*", "current": {"text": "All", "value": "$__all"}}
            ]}}
