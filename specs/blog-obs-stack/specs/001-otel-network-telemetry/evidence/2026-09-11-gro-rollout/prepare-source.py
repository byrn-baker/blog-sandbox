from pathlib import Path
import json,yaml
r=Path('/tmp/lab-gro-rollout');rows=json.loads(Path('/home/ubuntu/gro-rollout/leaf-audit.json').read_text())
for row in rows:
 nums=sorted(int(x.removeprefix('Ethernet')) for x in row['modeled'])
 assert nums==list(range(1,11)) and all(f'vmnicet{n}:' in row['linux'] for n in nums)
 data={'lab_gro_workaround':{'device':row['name'],'interfaces':nums,'gro':'off'}}
 p=r/'config_contexts/devices'/f"{row['name']}.yaml";p.parent.mkdir(exist_ok=True)
 assert not p.exists();p.write_text('# Lab vEOS workaround verified by captured TCP tests on 2026-09-11.\n'+yaml.safe_dump(data,sort_keys=False))
p=r/'golden-config/templates/eos/platform.j2';p.write_text(p.read_text()+'''{% if config_context.lab_gro_workaround is defined %}
{% set gro_fix = config_context.lab_gro_workaround %}
{% if gro_fix.device != hostname or gro_fix.gro not in ['off', 'on'] or not gro_fix.interfaces %}
{{ invalid_lab_gro_workaround_scope_or_state }}
{% endif %}
{% for interface_number in gro_fix.interfaces %}
{% if interface_number is not integer or interface_number < 1 or interface_number > 64 or ('Ethernet' ~ interface_number) not in (interfaces | map(attribute='name') | list) %}
{{ invalid_lab_gro_workaround_interface }}
{% endif %}
{# Only validated integers and enumerated states enter the shell action. #}
event-handler lab-gro-off-vmnicet{{ interface_number }}
   action bash sudo -n /sbin/ethtool -K vmnicet{{ interface_number }} gro {{ gro_fix.gro }}
   trigger on-boot
   delay 60
!
{% endfor %}
{% endif %}
''')
p=r/'jobs/gc_compliance_setup/__init__.py';s=p.read_text();s=s.replace('service routing protocols model\\nspanning-tree\\nvlan internal order','service routing protocols model\\nspanning-tree\\nvlan internal order\\nevent-handler lab-gro-off-');p.write_text(s)
d=yaml.safe_load((r/'tests/mock_contexts/arista_eos_leaf.yaml').read_text());d['hostname']='DCA-Leaf01';d['config_context']['lab_gro_workaround']={'device':'DCA-Leaf01','interfaces':[1,2],'gro':'off'}
(r/'tests/mock_contexts/arista_eos_gro.yaml').write_text(yaml.safe_dump(d,sort_keys=False))
for name,old,new in [('test_template_render.py','    ("arista_eos_spine.yaml", "arista_eos"),','    ("arista_eos_spine.yaml", "arista_eos"),\n    ("arista_eos_gro.yaml", "arista_eos"),'),('test_batfish_validate.py','        ("tests/mock_contexts/arista_eos_spine.yaml", "golden-config/templates/arista_eos.j2"),','        ("tests/mock_contexts/arista_eos_spine.yaml", "golden-config/templates/arista_eos.j2"),\n        ("tests/mock_contexts/arista_eos_gro.yaml", "golden-config/templates/arista_eos.j2"),')]:
 p=r/'tests'/name;s=p.read_text();assert old in s;p.write_text(s.replace(old,new))
p=r/'tests/test_template_render.py';p.write_text(p.read_text()+'''

@pytest.mark.parametrize("key,value", [
    ("device", "DCB-Leaf01"), ("gro", "off; reboot"),
    ("interfaces", []), ("interfaces", [True]), ("interfaces", [0]),
    ("interfaces", [65]), ("interfaces", ["1; reboot"]),
    ("interfaces", [64]),
])
def test_gro_rejects_unsafe_or_unmodeled_scope(key, value):
    context = load_context("arista_eos_gro.yaml")
    context["config_context"]["lab_gro_workaround"][key] = value
    with pytest.raises(jinja2.UndefinedError):
        build_jinja_env().get_template("golden-config/templates/arista_eos.j2").render(**context)


def test_gro_only_adds_handlers_and_can_restore_on():
    import re
    context = load_context("arista_eos_gro.yaml")
    template = build_jinja_env().get_template("golden-config/templates/arista_eos.j2")
    rendered = template.render(**context)
    assert rendered.count("event-handler lab-gro-off-vmnicet") == 2
    assert "ethtool -K vmnicet1 gro off" in rendered
    context["config_context"]["lab_gro_workaround"]["gro"] = "on"
    assert "ethtool -K vmnicet1 gro on" in template.render(**context)
    del context["config_context"]["lab_gro_workaround"]
    assert re.sub(r"event-handler lab-gro-off-vmnicet\\d+\\n(?:   .*\\n)+!\\n", "", rendered) == template.render(**context)
''')
