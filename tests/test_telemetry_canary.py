"""Canary scope and the actual IOS-XE record grammar."""
from pathlib import Path

import yaml

from tests.test_template_render import build_jinja_env, load_context

ROOT = Path(__file__).resolve().parents[1]


def test_ios_ipv4_protocol_and_export_before_attachment():
    text = build_jinja_env().get_template('golden-config/templates/cisco_ios.j2').render(
        **load_context('cisco_ios_ce_router.yaml'))
    assert '\n match ipv4 protocol\n' in text
    assert '\n match ip protocol\n' not in text
    assert text.index('flow monitor PART8-MONITOR') < text.index(' ip flow monitor PART8-MONITOR input')


def test_only_two_live_device_contexts_enable_canary():
    selected = []
    for path in (ROOT / 'config_contexts/devices').glob('*.yaml'):
        if 'telemetry_canary' in yaml.safe_load(path.read_text()):
            selected.append(path.stem)
    assert set(selected) == {'CE1', 'DCA-Leaf01'}


def test_ios_fleet_netflow_context_excludes_management():
    context = yaml.safe_load((ROOT / 'config_contexts/platform_cisco_iosxe.yaml').read_text())['netflow']
    assert context['destination'] == '192.168.3.241'
    assert context['port'] == 2055
    assert context['source_interface'] == 'GigabitEthernet1'
    assert 'GigabitEthernet1' not in context['interfaces']


def test_eos_fleet_sflow_context_uses_management_vrf():
    context = yaml.safe_load((ROOT / 'config_contexts/platform_arista_eos.yaml').read_text())['sflow']
    assert context == {
        'destination': '192.168.3.241',
        'vrf': 'MGMT-VRF',
        'source_interface': 'Management1',
        'port': 6343,
        'sample_rate': 16384,
    }


def test_ios_disabled_interfaces_do_not_get_monitor():
    context = load_context('cisco_ios_ce_router.yaml')
    for interface in context['interfaces']:
        if interface['name'] == 'GigabitEthernet6':
            interface['enabled'] = False
    text = build_jinja_env().get_template('golden-config/templates/cisco_ios.j2').render(**context)
    block = text.split('interface GigabitEthernet6\n', 1)[1].split('\n!', 1)[0]
    assert 'ip flow monitor' not in block


def test_eos_sflow_comparison_only_changes_run_state():
    context = load_context('arista_eos_leaf.yaml')
    context['config_context']['sflow']['enabled'] = True
    template = build_jinja_env().get_template('golden-config/templates/arista_eos.j2')
    before = template.render(**context)
    context['config_context']['sflow']['enabled'] = False
    after = template.render(**context)
    assert '\nsflow run\n' in before
    assert '\nno sflow run\n' in after
    assert before.replace('\nsflow run\n', '\nno sflow run\n') == after


def test_fleet_syslog_without_device_canary_context():
    for platform, mock, template, interface, commands in [
        ('cisco_iosxe', 'cisco_ios_ce_router.yaml', 'cisco_ios.j2', 'GigabitEthernet1',
         ['logging source-interface GigabitEthernet1 vrf MGMT-VRF',
          'logging host 192.168.3.241 vrf MGMT-VRF']),
        ('arista_eos', 'arista_eos_leaf.yaml', 'arista_eos.j2', 'Management1',
         ['logging vrf MGMT-VRF host 192.168.3.241',
          'logging vrf MGMT-VRF source-interface Management1']),
    ]:
        expected = {'destination': '192.168.3.241', 'vrf': 'MGMT-VRF',
                    'source_interface': interface}
        source = yaml.safe_load((ROOT / f'config_contexts/platform_{platform}.yaml').read_text())
        assert source['syslog'] == expected
        context = load_context(mock)
        context['config_context'].pop('telemetry_canary', None)
        assert context['config_context']['syslog'] == expected
        text = build_jinja_env().get_template('golden-config/templates/' + template).render(**context)
        for command in commands:
            assert text.splitlines().count(command) == 1
