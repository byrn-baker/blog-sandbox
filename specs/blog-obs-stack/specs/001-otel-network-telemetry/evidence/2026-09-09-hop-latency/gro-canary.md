# Proposed five-minute GRO canary

Status: executed with user approval; GRO was restored. See [results](../2026-09-09-gro-canary/README.md).
The following is the approved historical plan. Specific device-run approval is required by
[the lab conventions](/home/ubuntu/.kiro/steering/sp-demo-lab.md).

## Scope and preflight

DCA-Leaf01, management 192.168.3.32, Ethernet5, Linux device vmnicet5.
The Linux interface MAC 50:00:00:03:00:05 matches the live Ethernet5 MAC.
EVE's node 3 tap vunl0_3_5 connects this port to the master-2 fabric path;
the captured master MAC is 02:00:00:00:01:0b. The interface description still
says DCA-k3s-w1. Use the verified wiring and packet MAC, not that stale label.

The preflight verified generic-receive-offload is on, ethtool is /sbin/ethtool,
and systemd-run/systemctl are present. Their timer behavior has not yet been
tested. Recheck device identity, MAC, GRO state, K3s readiness and the independent
management connection before execution. Abort if any differs from this plan.

Only GRO on vmnicet5 is changed. Keep MTU, NIC model, CPU allocation, routing,
bond membership and other offloads unchanged to make the result interpretable.
The possible cost is higher packet-processing CPU on the leaf. Watch CPU,
BGP/EVPN state, packet loss and API transport; revert early if they deteriorate.

## Automatic restoration before the change

Using the existing privileged EOS session, choose a unique unit name for this
run and verify no service/timer with that name exists. The following name is
reserved for the proposed run only:

```text
bash sudo -n systemd-run --unit=lab-gro-canary-20260909 --on-active=300s /sbin/ethtool -K vmnicet5 gro on
bash sudo -n systemctl is-active lab-gro-canary-20260909.timer
```

Proceed only if timer creation succeeds and its state is active. A timer error
means abort before changing GRO. Preserve the management session for manual
restoration. Any Nautobot job used for execution must enable Fail Job on Task
Failure and inspect per-device results.

## Temporary change

```text
bash sudo -n /sbin/ethtool -K vmnicet5 gro off
bash sudo -n /sbin/ethtool -k vmnicet5
```

Verify generic-receive-offload is off. If verification fails, restore immediately.
This is a runtime experiment; it does not write startup configuration.

## Measurement and acceptance

1. Start matched header-only captures on master 2, worker 4 and EVE; verify each
   reports listening before sending probes. Use a fresh directory and fresh
   dedicated source ports, for example 48200-48223.
2. Send low-rate sequential HTTPS probes with the same 3-second timeout as the
   baseline. Record TCP/TLS/HTTP timings and return codes.
3. Classify every response by the actual leaf path in the EVE trace. Responses
   through unchanged DCA-Leaf02 provide a concurrent comparison. Do not alter
   host bond selection to force the treated path.
4. On the treated path, verify separate segments remain separate after VXLAN
   encapsulation, and the 1522-1524-byte combined packets disappear. Follow
   sequence ranges through the spine and to the worker, accounting for all
   retransmissions and selective acknowledgements.
5. Compare completion times, per-hop timings and CPU. Improvement requires
   reduced retransmission/delay on treated-path flows without new failures;
   successful HTTP alone is insufficient. Broad MTU-counter deltas include
   background traffic and must not be attributed entirely to the probes.
6. If too few responses take the treated path, record an inconclusive test.
   Do not extend the timer or expand scope without a new decision.

The test can validate this particular coalescing hypothesis; it cannot establish
fleet stability or guarantee that the normal 10-25 ms virtual-switch delays vanish.

## Restoration and follow-up

Restore early when measurement finishes, even if the automatic timer has not fired:

```text
bash sudo -n /sbin/ethtool -K vmnicet5 gro on
bash sudo -n /sbin/ethtool -k vmnicet5
```

Keep the timer as a redundant restoration until the original state is confirmed.
Verify the final GRO state, node readiness and a post-restoration probe batch.
Collect timer/service status without interpreting an expired transient unit's
absence alone as proof of restoration. Finish with the original state restored,
whether the test improves traffic or not.

If the canary works, prepare a persistent, source-controlled implementation,
including restart behavior and rollback, then request approval for the next
specific deployment wave. Do not turn this experiment into a fleet change.
