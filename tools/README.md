# Lab diagnostics

Run the read-only pyATS baseline with the existing Kiro connection settings:

```bash
python3 tools/lab_network_baseline.py \
  --settings /home/ubuntu/.kiro/settings/mcp.json \
  --output /tmp/lab-baseline-NEW-TIMESTAMP
```

Use a new output directory each time. Optionally select devices with
`--devices CE3 DCC-Leaf01`. The collector queries live Nautobot network roles,
checks testbed management addresses, and uses at most four simultaneous device
connections. It uses hostname learning and a 60-second connection timeout.
Initialization changes terminal pagination only; configuration initialization
is disabled. Credentials and session transcripts are not written to evidence.

Each command records its timestamp and outcome. Forwarding/discard counters are
sampled twice when preceding commands succeed, with at least ten seconds between
the last initial command and the repeat. Devices are sampled in batches, so this
is not a simultaneous fleet snapshot. Use the recorded times when calculating
rates. Counter decreases can indicate a reset and must not be treated as negative
loss. EOS physical and port-channel counters may describe the same packets;
do not sum them as independent losses.

The summary distinguishes successful commands from connection failures. An SSH
or pyATS exception is an incomplete observation, not evidence that a device is
down. JSON command outputs remain raw CLI text so parser failures cannot silently
turn missing data into healthy results.
