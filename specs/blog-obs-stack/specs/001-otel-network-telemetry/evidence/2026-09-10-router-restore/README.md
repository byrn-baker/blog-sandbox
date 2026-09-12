# Router restoration, 2026-09-10

The user authorized restoring all CML routers and testing interface MTU 9216
with IS-IS after the virtio migration. They separately approved publishing the
validated source to main and synchronizing Nautobot when automatic approval
review required explicit shared-source authorization.

## Source and validation

Commit 6a0d291 sets router_data_mtu to 9216 in the Cisco platform context,
renders it on data interfaces, and explicitly renders no shutdown for modeled
enabled interfaces. Management and NAT Outside interfaces are excluded from
this MTU policy. Explicit modeled interface MTUs take precedence.

The isolated checkout /tmp/router-virtio-source preserves unrelated work in the
primary checkout. make ci-full passed 62 template/structure tests and 149
Batfish/intended checks; four existing pytest deprecation warnings remained.
Nautobot repository sync 9ea8c392-c584-4c8b-8e84-514decb2656f succeeded.
Intent generation 71782a57-239e-4916-a6db-79603bee72f7 succeeded for all 13 routers.

## Completed canary

SP2 deployment 5d8e2d1d-6bc3-46a1-bd5a-b7ced9703cce ran from 03:02:40 to
03:09:26 UTC and succeeded. Fail Job on Task Failure was enabled. Per-device
logs confirm merge and save completion. Initial log filtering found only /31 mask cautions. A later transcript review
found rejected IPv6 IS-IS commands that the existing error pattern missed;
see the correction below. The SUCCESS result did not establish a full restore. Five data interfaces are up and saved
with mtu 9216. IS-IS NET 49.0001.0000.0004.0001.00 is saved. No IS-IS neighbors
were present because peers had not yet been restored. This is not a completed
IS-IS or jumbo forwarding test. See SP2-verified.json.

## Management recovery and interruption

The first backup job b0e73e20-6319-4916-8108-4c3dc969e021 failed on CE1, SP1,
SP4, SPE1 and SPE3 at TCP connectivity prechecks. The other eight backups
succeeded. Fresh compliance and intended Plans were prepared for those eight.

Console reads found SP1, SP4, SPE1 and SPE3 had MGMT-VRF but no management IP.
Static management IPs from live Nautobot were sent over their consoles.
The scripts did not observe save confirmation within their short read interval;
subsequent SP1 read-back proves its running and startup IP are 192.168.3.53/24.
Do not infer confirmed saves for the other three from that SP1 result.

CE1 had its correct static address but no management cable in CML. Adding a
port to the running shared management switch was rejected because its physical
configuration was locked. A dedicated external connector CE1-lab-mgmt on the
existing vlan3 bridge was created and linked to CE1 GigabitEthernet1. It reached
BOOTED and its link STARTED; CE1 carrier recovery was not verified.

The next deployment wave a633d5c1-c376-4d7d-9b1f-18e281eddab4 targeted BORDER1,
RR2 and SP3 with Fail Job on Task Failure enabled. All three failed at TCP
connection setup before sending configuration. Their Plans are Failed.

A subsequent CML read shows CE1 and mgmt-switch-0 STOPPED, and the new connector
absent. This agent did not stop those nodes or delete the connector. Further
writes paused while asking the user whether CML changes were in progress.
Recheck current state and obtain fresh backups/compliance/Plans after recovery;
do not blindly retry failed Plans. Current status is incomplete.

The EOS fabric MTUs and Linux transport ceilings remain separate concerns.
This router-only change does not establish a uniform end-to-end MTU of 9216.

## Resumed rollout and hidden IOS error

The user repaired CE1 management wiring to mgmt-switch-0 port13 and restored
carrier. Subsequent authenticated reads succeeded on 12 routers. SPE1 retained
a stale local/receive route for 192.168.3.21, the automation host's address,
despite its configured management address being 192.168.3.57. A console-based
shutdown, no ip address, static reapplication, no shutdown and save cleared the
stale route. Read-back confirmed the route was no longer receive, the interface
was up, save returned [OK], and SSH worked. All 13 routers became reachable.

The 14 modeled IS-IS core links match current CML wiring. Fresh preparation ran
after management recovery. SP1, RR2 and BORDER1 deployment jobs reported SUCCESS,
with matching running/startup data MTUs and enabled states. RR2-SP2 and SP1-SP2
formed Level-2 adjacencies. Three DF probes each at 9000 and 9216 bytes passed
on RR2-SP2, SP1-SP2 and both BORDER1 core links. The first 1500-byte BORDER1-SP1
sample was not 3/3; it must not be reported as fully passing.

A deeper transcript review found the exact CLI rejection:

    %ISIS: IPv6 unicast routing not enabled

The plan's feature order put interfaces before the global IPv6 enable, even
though the source entry template already put global routing first. The deployed
error regex only recognized failures with a space after %, so %ISIS: failures
were missed. Earlier SUCCESS and save results prove MTU/port restoration, not
successful IPv6 IS-IS activation. BORDER1's brief adjacency disappeared after its
IS-IS level was configured; its persistent absence is not explained by the
successful unicast jumbo probes or by the identified IPv6 error alone.

Correction commit 6a3fd2e orders routing_global (045), isis (055), and interfaces
(060), aligns the entry template, and detects the exact IOS prerequisite error.
It passed 64 structure/render tests and 149 Batfish/config checks. Automatic
approval review rejected publishing this second commit because the earlier
approval named only the first commit. Publication approval was requested.
RR1, SP3, SP4 and SPE3 jobs were already in flight when the error was found;
no additional device wave was launched after discovery pending corrected plans.


## Corrected rollout checkpoint, 04:12 UTC

The user approved commit 6a3fd2e. Publication and Nautobot sync completed;
repository sync a29db512-11cd-40a6-ab56-c105b361438d and the active Git loader
job d94a3972-9bed-4f88-bf40-f041bf5d50dc succeeded. Live feature ordering
was verified before fresh intent, backup, compliance and missing plans.

BORDER1, RR1, RR2, SP1, SP2, SP3, SP4 and SPE3 completed their corrected plans.
Read-back confirmed modeled data MTUs and enabled states, plus IPv6 IS-IS
activation, in both running and startup configurations on all eight routers.
Eight of the 14 core links have adjacencies. Four more links await SPE1 and
SPE2 restoration; BORDER1's two links remain down. Counts at different
snapshot times should not be combined into an assumed simultaneous total.

SPE1 canary job 0862382c-cb77-4512-bd74-addfc70a97dd failed at the exact
command `passive-interface Loopback0`: IOS rejected it because the virtual
interface did not yet exist. The job stopped and did not save. Its running
configuration is partially restored, not a completed deployment. No stale
retry was attempted. Commit 57906da adds an early Loopback0 prerequisite
feature and renders Loopback0 before router IS-IS. The later interfaces
feature can safely re-enter the same loopback. Validation passed 65 template
and structure tests plus 149 Batfish/config tests. Automatic approval review
rejected publication because prior approvals covered only prior commits;
explicit approval for this commit and sync is pending.

CE1, CE2 and CE3 have no IS-IS dependency. Their reviewed plans were launched
as separate jobs with fail_job_on_task_failure enabled:
CE1 4bfc8240-627e-48d8-b0a9-7d62f60a7255,
CE2 b8582f8e-1012-4630-b7f3-f11f688caba4,
CE3 e7738f2e-8cbb-4237-84c7-c1367e415b25.
These were still active at this checkpoint.

BORDER1's data interfaces remain physically up/up with CLNS MTU 9213 over
interface MTU 9216, but IS-IS internally reports `if state DOWN`. PTP hello
counters remain at 8 sent / 2 received. A scoped `clear isis SP-ISIS *`
and a brief shutdown/no shutdown of Gi2 and Gi3 did not recover the internal
state. Both interfaces returned up/up and the intended enabled state remains
saved. The cause is unresolved; successful unicast jumbo probes do not prove
IS-IS multicast forwarding. No router reboot was performed for this issue.


## CE completion and BORDER1 follow-up

CE1, CE2 and CE3 jobs all completed SUCCESS, with save completion and no
matched IOS rejection in the transcript scans. Authenticated read-back confirmed
all modeled data MTUs and enabled states in both running and startup configs.
This brings verified router MTU/port restoration to 11 of 13. CE routers do not
run IS-IS; their empty neighbor tables are expected, not core adjacency results.

DF probes across the ten core links between the eight restored core routers
passed 3/3 at both 9000 and 9216 bytes on every link. Eight links also passed
3/3 at 1500 bytes. BORDER1's two first 1500-byte samples lost a packet; these
must not be represented as full passes. Four core links remain untested because
SPE1 and SPE2 restoration is unfinished. The saved per-device probe JSON files
contain the measured results.

A final bounded BORDER1 recovery detached and restored its existing IPv4 and
IPv6 IS-IS interface bindings. IOS also reset the per-interface IS-IS network
mode during that operation, so `isis network point-to-point` was explicitly
restored on Gi2 and Gi3. A full command-set comparison then found no differences
between running and startup on either interface. IS-IS still reports internally
DOWN with zero neighbors. This attempt did not resolve the fault. No additional
recovery changes are active or left pending on BORDER1.

Remaining work: obtain publication approval for 57906da, sync and rerun the
active compliance loader, regenerate intent/backups/compliance and fresh PE
plans, verify SPE1 before SPE2, and resolve BORDER1's missing adjacencies.
The current checkpoint is not a completed network stabilization result.


Fresh checkpoint backup 30dee5ef-c9d6-4efd-a842-b69ea332b14a and compliance
47dea13c-ecf6-41b1-838a-758f5bb40dfb both completed SUCCESS. This reports job
execution, not clean compliance. Every router still has feature drift; see
checkpoint-compliance-summary.json. Restored routers retain interface/ACL
representation differences and core routers show IS-IS drift. BORDER1's
running router IS-IS block lacks passive-interface Loopback0 while its loopback
has explicit IP and IPv6 IS-IS activation. This configuration interaction still
needs reconciliation; MTU and active-core-interface checks do not prove full
intended-config compliance. CE routers and SPE3 also show BGP feature drift,
which has not yet been classified. No pending source publication was performed.
