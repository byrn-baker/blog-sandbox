from netclaw_compliance import normalize


def test_hidden_default_only():
    raw = "interface Loopback0\n ip address 1.1.1.1 255.255.255.255\n no shutdown"
    assert normalize(raw, "interfaces", "cisco_ios") == raw.removesuffix("\n no shutdown")
    assert " shutdown" in normalize("interface GigabitEthernet2\n shutdown", "interfaces", "cisco_ios")
    assert normalize("interface Loopback0", "interfaces", "cisco_ios") != normalize("", "interfaces", "cisco_ios")


def test_pagination_keeps_security_and_other_parents():
    raw = "line vty 0 4\n length 0\n transport input ssh\n exec-timeout 5 0\ninterface Ethernet1\n length 0"
    out = normalize(raw, "vty", "cisco_ios")
    assert "transport input ssh" in out and "exec-timeout 5 0" in out
    assert out.count("length 0") == 1
    assert normalize(raw, "vty", "arista_eos") == raw


def test_acl_order_untouched():
    raw = "ip access-list standard TEST\n 10 deny any\n 20 permit any"
    assert normalize(raw, "acl", "cisco_ios") == raw
