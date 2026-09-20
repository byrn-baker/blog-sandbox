"""Send bounded protocol-valid test traffic; uses no device credentials.

Run on the automation host for management, and on a lab VM with --bind set
to its bond0 address. TEST-NET-style benchmark addresses identify synthetic
flow content; they are never used as real packet destinations.
"""
import argparse
import socket
import struct
import time


def packets(label):
    number = {"management": 1, "lab": 2}[label]
    source = socket.inet_aton(f"198.18.0.{number}")
    destination = socket.inet_aton("198.18.1.1")
    now = int(time.time())
    # One NetFlow v5 record, exported with a current boot-relative time.
    header = struct.pack("!HHIIIIBBH", 5, 1, 100000, now, 0, 1, 0, 0, 0)
    record = struct.pack("!4s4s4sHHIIIIHHBBBBHHBBH", source, destination,
                         b"\0" * 4, 1, 2, 1, 64, 99000, 100000,
                         42000 + number, 443, 0, 0, 6, 0, 0, 0, 24, 24, 0)
    # sFlow v5 raw Ethernet/IPv4/UDP flow sample.
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 28, 1, 0, 64, 17, 0, source, destination)
    udp = struct.pack("!HHHH", 43000 + number, 443, 8, 0)
    frame = b"\x02\0\0\0\0\x01\x02\0\0\0\0\x02\x08\0" + ip + udp
    raw = struct.pack("!IIII", 1, len(frame), 0, len(frame)) + frame
    raw += b"\0" * (-len(raw) % 4)
    sample = struct.pack("!IIIIIIII", 1, 1, 1, 1, 0, 1, 2, 1) + struct.pack("!II", 1, len(raw)) + raw
    sflow = struct.pack("!II4sIIII", 5, 1, source, 0, 1, 100000, 1) + struct.pack("!II", 1, len(sample)) + sample
    syslog = ("<134>" + time.strftime("%b %d %H:%M:%S", time.gmtime()) +
              f" part8-gate part8-gate-{label}").encode()
    return {2055: header + record, 6343: sflow, 514: syslog}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vip", required=True)
    p.add_argument("--bind", required=True)
    p.add_argument("--label", choices=["management", "lab"], required=True)
    args = p.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((args.bind, 0))
        for port, packet in packets(args.label).items():
            s.sendto(packet, (args.vip, port))
            print(f"Sent {len(packet)} bytes from {args.bind} to {args.vip}:{port}")
