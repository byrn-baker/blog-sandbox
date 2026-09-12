# BORDER1 IS-IS investigation, 2026-09-10 evening

The user asked why BORDER1 IS-IS is broken. This investigation has localized
the failure to BORDER1's local protocol processing, but has not established
the exact software defect or initiating command. No routing configuration
was changed in this investigation. Temporary captures and adjacency debugs
were stopped. A configuration-based diagnostic is prepared and awaiting approval.

## Confirmed observations

Both BORDER1 core links are physically up and correctly wired in CML:
Gi2 to SP1 Gi6, Gi3 to SP2 Gi6. Earlier completed forwarding tests passed
1500/9000/9216-byte DF probes on both links; those are historical tests, not
fresh ICMP samples from this evening's investigation.

Data MTU is 9216 and CLNS MTU 9213 at both ends. Effective IS-IS settings
match working peers: level-2 router type, level-1-2 interface circuit type,
point-to-point mode, 10-second hellos, multiplier three, padding enabled,
IPv4/IPv6 enabled, and no interface authentication. Global IP and CLNS routing
are enabled. No protocol shutdown or passive physical interfaces were found.

A roughly 35-second CLNS-only capture recorded four 9229-byte Ethernet frames
containing IS-IS point-to-point hellos from SP1 on its BORDER1 link and four
from SP2 on its BORDER1 link. None were sent by BORDER1. BORDER1 did send one
60-byte ES-IS frame on the SP1 link. The working SP1-SP2 control capture recorded
five SP1 and four SP2 IS-IS hellos with the same 9229-byte frame size (9212-byte
IS-IS PDU). Therefore this is not evidence of a universal CML inability to carry
jumbo IS-IS frames. Captures contain only LLC CLNS traffic, not IP application
payloads. packet-summary.json preserves decoded protocol headers and counts.

BORDER1's CLNS IS-IS punt policer showed 16,787 conforming packets and zero
drops, later increasing to 16,858. The IOS RP infrastructure counter also
recorded CLNS IS-IS control packets, with no reported punt header/length/link
errors. CLNS input accounting was 16,783 packets while the IS-IS PTP hello
counters remained 11 sent / 2 received. The CLNS aggregate also includes ES-IS;
these cumulative counters alone are not a per-packet trace through IOS.

A 35-second adjacency debug on BORDER1 produced no IS-IS send/receive messages.
The same method on SP1 produced 248 matching diagnostic lines, including sends
toward BORDER1 and normal receive/state processing on working links. The SP1
collector hit a ReadTimeout during a later read after its debug-off command;
a fresh show debugging on both routers confirmed the debug is off. The partial
collector failure does not erase the captured positive-control messages.

IS-IS processes exist and are scheduled, reporting Waiting for Event. BORDER1
has approximately 1.41 GB of free IOS processor memory and no reported buffer
allocation failures. Its 18,024-byte huge-buffer pool was free, matching the
healthy peer's available pool. Memory exhaustion and punt policing were not
supported by these samples.

## Interpretation and corrections

The strongest current explanation is a local IOS IS-IS state/processing fault.
The approved small-hello test below also failed, weakening the jumbo-hello handling explanation.
The absence of transmitted hellos and their processing, despite matching
configuration, is more informative than simply displaying if state DOWN.

Earlier restoration notes called if state DOWN an internal failure indication.
That was too strong: SP1/SP2 also display DOWN on their non-adjacent BORDER1
links while continuing to send hellos. The field itself is an adjacency state,
not proof of a hung process. BORDER1's frozen zero-second hello timer and
non-progressing hello counters are the relevant additional observations.

Historical logs show the first SP2 adjacency at 03:36:30, a BORDER1 all-adjacencies
clear at 03:36:34, and peer expiry 30 seconds later. A later bounded protocol
restart briefly emitted hellos at 04:34:07 and peers expired again at 04:34:37.
These correlate with earlier restoration/recovery activity, but the exact
command or defect causing the persistent fault has not been proven. No vendor
bug identifier is claimed.

## Approved small-hello diagnostic result

The user approved and we executed a temporary change on SP1 GigabitEthernet6:

    interface GigabitEthernet6
     no isis hello padding always

During approximately 63 seconds of observation, six BORDER1 neighbor checks
remained empty. The capture proves SP1 sent seven 118-byte IS-IS point-to-point
hello frames. BORDER1 emitted no IS-IS hellos. Its PTP sent/received counters
remained 11/2 while aggregate CLNS input increased from 16968 to 16988.
Small hellos therefore did not restore processing or adjacency. This strengthens
the local IS-IS state/processing fault hypothesis; it does not identify a vendor
bug or prove the command that initiated the fault.

The finally block restored SP1 Gi6 using isis hello padding. Full interface
configuration matched before/after exactly. A separate fresh connection verified
that match again, startup Gi6 still has MTU 9216 with no padding override, and
show debugging reported no active debugging. No startup save was issued. All three diagnostic CML
captures were confirmed stopped. MTU remained 9216 throughout.

Results are in small-hello-canary.json and small-hello-canary.pcap, with decoded
frames in packet-summary.json. SP1-hello-cleanup.json and capture-cleanup.json
record the independent cleanup checks.

A controlled BORDER1 reload is the next recovery candidate after earlier
adjacency clears, interface resets and protocol toggles failed to give durable
recovery. It has not been executed or approved in this test. Before a reload,
compare running and startup state and preserve any differences; after it,
verify both peers, hello counters, routes and reachability with MTU 9216 retained.

## Capture client correction

The installed virl2 client builds pcap download URLs with /api/v0 duplicated.
Capture start/status worked, but the first download returned 404. Retrieval was
corrected locally to /api/v0/pcap/<link-id> and performed while capture was active,
before stop_capture clears its state. No installed library was modified. The
initial failed attempt was not counted as packet-loss evidence.

## Reference

Cisco's [IOS XE adjacency troubleshooting guide](https://www.cisco.com/c/en/us/support/docs/ip/integrated-intermediate-system-to-intermediate-system-is-is/220649-troubleshoot-is-is-adjacency-issues.html)
describes checking wiring, matching MTUs/circuit types, CLNS state and adjacency
debugs. The [IS-IS command reference](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/iproute_isis/command/irs-cr-book/irs-a1.html)
documents the interface-level no isis hello padding always diagnostic distinction.
