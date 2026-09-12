# BORDER1 reload recovery, 2026-09-11

The user explicitly approved a controlled BORDER1 reboot. Before reload,
BORDER1 had no IS-IS neighbors and PTP hello counters remained 11 sent / 2
received. All non-certificate running and startup configuration matched;
the remaining difference was certificate representation. No configuration
save or network configuration change was issued. The graceful reload was
confirmed through IOS CLI at approximately 02:46:29 UTC.

Management SSH was unavailable during startup. CML console logs showed a normal
IOS XE 17.15.1a boot. After management returned, both SP1 on Gi2 and SP2 on Gi3
were UP. Independent checks on both peers also showed BORDER1 UP.

BORDER1 learned 21 IPv4 and 21 IPv6 IS-IS prefixes. Gi2 and Gi3 were up/up at
MTU 9216, and their running interface configurations exactly matched pre-reload.
Three 9216-byte DF pings to each peer succeeded (6/6 total). The first successful
hello-counter sample was 12/8 and a later check reached 28/26.

The recovery with the saved network configuration supports a local runtime
state/processing fault. It does not identify a specific software defect or the
command that originally triggered the failure. Full configuration hashes differ
across boot; only the stated preflight comparison and data-interface equality
were verified. K3s and the rest of the fleet were not audited during this run.

Seven subsequent samples from 02:52:13 through 02:54:17 UTC all showed both
neighbors UP. PTP hello counters advanced from 26/22 to 54/50 during that
124-second observation, beyond the previous 30-second failure window. This is
a bounded stability check, not proof of long-term immunity to recurrence.
