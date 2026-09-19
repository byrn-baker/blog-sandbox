"""Exception-oriented Grafana landing page for network operations."""


def dashboard(expected_devices):
    ds = {"type": "prometheus", "uid": "network-snmp"}
    normal_interfaces = 'job="snmp",if_type!="",if_type!="166",interface!~"(VoIP-)?Null0"'

    def stat(panel_id, title, expression, x, color="red"):
        return {
            "id": panel_id, "title": title, "type": "stat", "datasource": ds,
            "gridPos": {"x": x, "y": 0, "w": 4, "h": 4},
            "targets": [{"refId": "A", "expr": expression, "instant": True}],
            "fieldConfig": {"defaults": {"unit": "short", "thresholds": {"mode": "absolute", "steps": [
                {"color": "green", "value": None}, {"color": color, "value": 1}
            ]}}, "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "textMode": "value_and_name"},
        }

    def table(panel_id, title, expression, x, y, width, height, columns, description=""):
        names = [name for name, _ in columns] + ["Value"]
        rename = {name: label for name, label in columns}
        rename["Value"] = title
        return {
            "id": panel_id, "title": title, "type": "table", "datasource": ds,
            "description": description, "gridPos": {"x": x, "y": y, "w": width, "h": height},
            "targets": [{"refId": "A", "expr": expression, "instant": True, "format": "table"}],
            "transformations": [
                {"id": "filterFieldsByName", "options": {"include": {"names": names}}},
                {"id": "organize", "options": {"indexByName": {name: i for i, name in enumerate(names)},
                                                   "renameByName": rename}},
            ],
            "fieldConfig": {"defaults": {}, "overrides": []},
            "options": {"showHeader": True},
        }

    panels = [
        stat(1, "Devices stale", f'clamp_min(vector({expected_devices}) - (count(max by (device) '
             '(timestamp(snmp_device_uptime_ticks{job="snmp"})) > time() - 180) or vector(0)), 0)', 0),
        stat(2, "Interfaces unexpectedly down", f'count(snmp_interface_oper_status{{{normal_interfaces}}} != 1 '
             'and on(device,if_index) snmp_interface_admin_status{job="snmp"} == 1) or vector(0)', 4),
        stat(3, "BGP peers not established", 'count(snmp_bgp_peer_state{job="snmp",vrf!=""} != 6) or vector(0)', 8),
        stat(4, "IS-IS adjacencies not up", 'count(snmp_isis_adjacency_state{job="snmp"} != 3) or vector(0)', 12),
        stat(5, "BFD rows not up", 'count(snmp_bfd_session_state{job="snmp"} != 4) or vector(0)', 16),
        stat(6, "Poll errors (5m)", 'sum(increase(otelcol_scraper_errored_metric_points{receiver=~"snmp/.*"}[5m])) or vector(0)', 20),
        table(7, "Unexpectedly down interfaces",
              f'snmp_interface_oper_status{{{normal_interfaces}}} != 1 '
              'and on(device,if_index) snmp_interface_admin_status{job="snmp"} == 1',
              0, 4, 12, 8, [("site", "Site"), ("device", "Device"), ("role", "Role"), ("interface", "Interface")],
              "Interfaces are shown only when administratively enabled but operationally not Up."),
        table(8, "Routing exceptions",
              'label_replace(max by(site,device,vrf,peer)(snmp_bgp_peer_state{job="snmp",vrf!=""} != 6), '
              '"protocol", "BGP", "device", ".*")',
              12, 4, 12, 8, [("site", "Site"), ("device", "Device"), ("protocol", "Protocol"),
                              ("vrf", "VRF"), ("peer", "Peer")],
              "BGP exceptions are listed here. IS-IS and BFD detail remains on Network Routing until their peer identity is consistent."),
        table(9, "Most utilized inbound interfaces",
              f'topk(15, 100 * rate(snmp_interface_in_octets_total{{{normal_interfaces}}}[5m]) * 8 / '
              f'(snmp_interface_speed_mbps{{{normal_interfaces}}} * 1000000 > 0))',
              0, 12, 12, 9, [("site", "Site"), ("device", "Device"), ("role", "Role"),
                              ("interface", "Interface")],
              "Uses SNMP-reported speed. Treat virtual-interface utilization as advisory."),
        table(10, "Interfaces with errors or discards",
              f'topk(15, rate(snmp_interface_in_errors_total{{{normal_interfaces}}}[5m]) + '
              f'rate(snmp_interface_out_errors_total{{{normal_interfaces}}}[5m]) + '
              f'rate(snmp_interface_in_discards_total{{{normal_interfaces}}}[5m]) + '
              f'rate(snmp_interface_out_discards_total{{{normal_interfaces}}}[5m])) > 0',
              12, 12, 12, 9, [("site", "Site"), ("device", "Device"), ("role", "Role"),
                               ("interface", "Interface")],
              "Combined error and discard rate highlights interfaces for drill-down. It is not a packet-loss percentage."),
        table(11, "Device sample age",
              'time() - max by(site,device,role,platform)(timestamp(snmp_device_uptime_ticks{job="snmp"}))',
              0, 21, 12, 7, [("site", "Site"), ("device", "Device"), ("role", "Role"),
                              ("platform", "Platform")],
              "Sample age for devices that still have a series in the selected time range. The fleet count detects fully absent devices."),
        table(12, "BGP transitions into Established (1h)",
              'increase_prometheus(snmp_bgp_peer_established_transitions_total{job="snmp",vrf!=""}[1h]) > 0',
              12, 21, 12, 7, [("site", "Site"), ("device", "Device"), ("vrf", "VRF"),
                               ("peer", "Peer")],
              "A transition is evidence of session activity, not the reason. Correlate it with syslog when event ingestion is available."),
    ]
    # Collector self-metrics are scraped into the cluster store only.
    panels[5]["datasource"] = {"type": "prometheus", "uid": "VictoriaMetrics"}
    for panel_id, unit in [(9, "percent"), (10, "suffix: events/s"), (11, "s")]:
        panels[panel_id - 1]["fieldConfig"]["defaults"]["unit"] = unit
    return {
        "uid": "network-operations", "title": "Network Operations Overview",
        "description": "Exception-oriented NOC landing page. Use Network SNMP and Network Routing for drill-down.",
        "tags": ["network", "noc", "snmp"], "schemaVersion": 39, "version": 1,
        "editable": False, "timezone": "browser", "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"}, "panels": panels,
        "links": [
            {"title": "Network SNMP", "type": "link", "url": "/d/network-snmp", "keepTime": True},
            {"title": "Network Routing", "type": "link", "url": "/d/network-routing", "keepTime": True},
        ],
    }
