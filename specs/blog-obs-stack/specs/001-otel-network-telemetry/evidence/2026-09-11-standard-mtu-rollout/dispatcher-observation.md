# Multi-device save overlap

The approved spine wave a3aeef0c-71a6-4af6-8fc7-adbc910f2fb7 failed on
DCB-Spine01 and DCC-Spine02. DCB-Spine01 timed out matching `end` during the
merge. Its running and startup MTUs already matched intent. DCC-Spine02 had
two remaining interfaces after the failed wave: Ethernet3 and Ethernet10.

The installed nornir_nautobot NetmikoDefault.merge_config implementation calls
`task.nornir.with_processors([]).run(task=netmiko_save_config, confirm=True,
raise_on_error=True)` from each device task without filtering to that host.
Thus each merge can start saves across the selected inventory, overlapping
other merges and saves. Job logs show copy commands interleaved in merge
output. This is evidence of a dispatcher concurrency problem, not an MTU
command rejection. The dependency was not patched during this rollout.

Recovery used fresh backups (0246502b-9082-4ea1-aee2-15c1daf8da31), a new
source-derived plan for only DCC-Spine02's two remaining interfaces, and a
single-device deployment (eb1e1f14-0f46-4d5e-85f3-3c51917a62ad). That job
succeeded. Both failed-wave devices were verified independently against
running and startup MTUs and all four expected underlay peers. Remaining
switches deploy as individual jobs with Fail Job on Task Failure enabled.
The original failed job remains a failure in the record.
