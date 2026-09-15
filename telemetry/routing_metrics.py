"""Polled routing objects verified on the lab's IOS-XE and EOS images.

These are IPv4 BGP peers in default and explicitly verified EOS VRF contexts,
plus Cisco IS-IS/BFD tables. They aren't an address-family or prefix inventory.
"""
BGP_ROLES = {'Border-Router', 'CE-Router', 'PE-Router', 'Route-Reflector', 'Leaf', 'Spine'}
CORE_ROLES = {'Border-Router', 'P-Router', 'PE-Router', 'Route-Reflector'}
ISIS = '1.3.6.1.4.1.9.10.118.1'
BFD = '1.3.6.1.4.1.9.10.137.1.2.1'


def extend_receiver(config, device):
    attributes, metrics = config['attributes'], config['metrics']

    def column(name, oid, labels, description, counter=False, unit='1'):
        metric = {'description': description, 'unit': unit,
                  'column_oids': [{'oid': oid, 'attributes': [{'name': x} for x in labels]}]}
        metric['sum' if counter else 'gauge'] = ({'aggregation': 'cumulative', 'monotonic': True,
            'value_type': 'int'} if counter else {'value_type': 'int'})
        metrics[name] = metric

    if device.get('role') in BGP_ROLES:
        attributes.update({'peer': {'oid': '1.3.6.1.2.1.15.3.1.7'},
                           'remote_as': {'oid': '1.3.6.1.2.1.15.3.1.9'}})
        for name, suffix, counter, unit, description in [
            ('state', 2, False, '1', 'BGP4-MIB peer state: 1 Idle, 2 Connect, 3 Active, 4 OpenSent, 5 OpenConfirm, 6 Established'),
            ('uptime_seconds', 16, False, 's', 'Seconds in Established state; IPv4 peer transport in the labeled VRF'),
            ('established_transitions_total', 15, True, '1', 'Transitions into Established; not a count of every intermediate state change'),
        ]:
            column('snmp_bgp_peer_'+name, '1.3.6.1.2.1.15.3.1.'+str(suffix), ['peer','remote_as'], description, counter, unit)
    if device['platform'] == 'cisco_iosxe' and device.get('role') in CORE_ROLES:
        attributes.update({'isis_adjacency': {'indexed_value_prefix': 'adj'},
                           'circuit_id': {'indexed_value_prefix': 'circuit'},
                           'bfd_session': {'indexed_value_prefix': 'bfd'},
                           'address_family': {'oid': BFD+'.13'},
                           'local_discriminator': {'oid': BFD+'.3'},
                           'application_id': {'oid': BFD+'.2'}})
        column('snmp_isis_adjacency_state', ISIS+'.6.1.1.2', ['isis_adjacency'],
               'Cisco IS-IS adjacency: 1 Down, 2 Initializing, 3 Up, 4 Failed')
        column('snmp_isis_circuit_if_index', ISIS+'.3.2.1.2', ['circuit_id'],
               'Dynamic IS-IS circuit to IF-MIB index mapping, including configured circuits without neighbors')
        column('snmp_bfd_session_state', BFD+'.6', ['bfd_session','address_family','local_discriminator','application_id'],
               'Cisco BFD state: 1 AdminDown, 2 Down, 3 Init, 4 Up, 5 Failing; not supported by the EOS profile')
        # This image reports internal interface handles in ciscoBfdSessInterface,
        # not valid IF-MIB indices. Do not attach incorrect interface names.
    return config


def index_transform():
    """Give dynamic numeric mapping values the same labels as existing IF-MIB rows."""
    return {'error_mode': 'propagate', 'metric_statements': [{'context': 'datapoint', 'statements': [
        'set(datapoint.attributes["if_index"], Concat(["if", String(datapoint.value_int)], ".")) where metric.name == "snmp_isis_circuit_if_index"',
        'set(datapoint.attributes["vrf"], "default") where IsMatch(metric.name, "^snmp_bgp_peer_") and datapoint.attributes["vrf"] == nil'
    ]}]}
