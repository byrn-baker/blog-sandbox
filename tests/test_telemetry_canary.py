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
