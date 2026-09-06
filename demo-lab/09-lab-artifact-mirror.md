# 09 — Lab Artifact Mirror

Large downloads do not go through the lab. They get staged on the automation
host and pulled over the management VLAN instead.

## Why

The servers default-route out through the emulated fabric:

```
bond0 -> Arista leaf (vEOS) -> spine -> CE -> SPE -> MPLS core -> BORDER1 -> NAT
```

Every hop is software forwarding inside a nested VM. Measured on 2026-09-04
with the k3s release binary as the payload:

| Source | Path | Rate |
|--------|------|------|
| DCA-k3s-m1 | bond0, through the fabric | 11.2 KB/s |
| DCB-k3s-w1 | bond0, through the fabric | 14.2 KB/s |
| DCC-k3s-w4 | bond0, through the fabric | 17.3 KB/s |
| blog-demo-vm | eth0, straight out | 44.7 MB/s |

The k3s binary is 66,400,408 bytes. At those rates a single node needs 62 to 96
minutes, and the k3s install script gives up long before that. This is what the
`Install K3s as the initializing server` task was failing on.

The rates above were measured while two EVPN sessions were flapping (see the
known-issues section of
[08-hypervisor-interconnect.md](08-hypervisor-interconnect.md)), but DC-C had a
clean control plane at the time and was still the slowest of the three. The
ceiling is the emulated dataplane, not the flap.

Meanwhile every server has `eth0` on the flat lab management VLAN, the same
VLAN 3 that Nautobot and Ansible already use to reach them. On DCA-k3s-m1:

```
$ ip route get 192.168.3.21
192.168.3.21 dev eth0 src 192.168.3.63
```

No fabric hop. Both endpoints are virtio NICs on the same Proxmox bridge, so a
pull from the automation host runs at bridge speed:

```
k3s      66400408B in 0.054498s = 1218400822 B/s
airgap  143833389B in 0.097025s = 1482436372 B/s
```

63 MB in 54 milliseconds instead of 96 minutes.

## What runs

`lab-mirror.service` on blog-demo-vm, a read-only static file server bound to
the VLAN 3 address:

```
ExecStart=/usr/bin/python3 -m http.server 8888 --bind 192.168.3.21 \
          --directory /home/ubuntu/lab-mirror
```

The unit source is kept at `/home/ubuntu/lab-mirror/lab-mirror.service` and
installed to `/etc/systemd/system/`. It runs as `ubuntu` with
`ProtectSystem=strict`, `ProtectHome=read-only`, and `NoNewPrivileges`, so the
server process cannot write anywhere.

**There is no authentication.** It is bound to the management VLAN address only
and serves static files. Do not put anything sensitive under
`/home/ubuntu/lab-mirror`.

```bash
systemctl status lab-mirror
curl -s http://192.168.3.21:8888/            # directory index
```

## Layout

```text
/home/ubuntu/lab-mirror/
  lab-mirror.service                        unit source
  k3s/
    install.sh                              from get.k3s.io, version-independent
    v1.30.5+k3s1/
      k3s                                   66,400,408 B
      k3s-airgap-images-amd64.tar.zst       143,833,389 B
      sha256sum-amd64.txt                   440 B
```

The version directory keeps the upstream name including the `+`. A literal `+`
in a URL path is fine (the plus-means-space rule only applies to query strings),
and both `curl` and Ansible's `get_url` handle it. Verified, not assumed.

`sha256sum-amd64.txt` is the upstream file and already contains entries for both
`k3s` and `k3s-airgap-images-amd64.tar.zst`, so one checksum URL covers both
downloads:

```yaml
checksum: "sha256:{{ k3s_mirror_url }}/{{ k3s_version }}/sha256sum-amd64.txt"
```

`get_url` matches the line by the destination filename.

## How Ansible consumes it

`ansible/group_vars/all.yml` sets the base:

```yaml
lab_mirror_url: "http://192.168.3.21:8888"
```

`ansible/group_vars/k3s_cluster.yml` narrows it:

```yaml
k3s_mirror_url: "{{ lab_mirror_url }}/k3s"
```

The `k3s_artifacts` role puts the binary at `/usr/local/bin/k3s`, the install
script at `/usr/local/share/k3s-install.sh`, and the image bundle in
`/var/lib/rancher/k3s/agent/images/`. Those are the paths the upstream installer
already defaults to, which is what lets `k3s_server` and `k3s_agent` run it with
`INSTALL_K3S_SKIP_DOWNLOAD=true` and make zero network calls. With that variable
set the script skips both the binary download and the SELinux RPM lookup, and
only checks that `/usr/local/bin/k3s` is executable.

The airgap bundle matters as much as the binary. Without it k3s pulls `pause`,
`coredns`, `local-path-provisioner`, `metrics-server` and `servicelb` from
docker.io on first start, which is another 137 MB back over the slow path.

Two consequences worth remembering:

`INSTALL_K3S_VERSION` no longer does anything, because it only ever fed the
download URL. The version installed is whichever binary sits under
`{{ k3s_mirror_url }}/{{ k3s_version }}/`. `k3s_version` in
`group_vars/k3s_cluster.yml` still selects it, just through the mirror path.

The "already installed" guards in `k3s_server` and `k3s_agent` key on the
systemd unit (`/etc/systemd/system/k3s.service`,
`/etc/systemd/system/k3s-agent.service`), not on the binary. The binary is now
present before the installer ever runs, so a `creates: /usr/local/bin/k3s` guard
would skip the install on a fresh node and leave you with a staged binary and no
cluster.

`k3s_artifacts` is listed in the same plays as `k3s_server` and `k3s_agent`
rather than in a play of its own. Role defaults only apply to the play the role
runs in, so a separate play would leave `k3s_install_script_path` undefined.

## Adding another artifact

1. Drop the file under `/home/ubuntu/lab-mirror/<tool>/<version>/` on
   blog-demo-vm, which has full-speed internet.
2. Stage a checksum file next to it so Ansible can verify. Prefer the upstream
   one if it exists.
3. Fetch it with `get_url` against `{{ lab_mirror_url }}/...` and a `checksum:`
   pointing at that file.
4. Confirm the consuming host reaches it over `eth0`:
   `ip route get 192.168.3.21` should say `dev eth0`.

Anything above roughly a megabyte is worth staging. Below that the fabric is
merely annoying rather than fatal.

## Adding a Helm chart

`/home/ubuntu/lab-mirror/helm/` is one flat directory of `.tgz` files plus a
generated `index.yaml`, not a real Helm repository server. Two different
consumers read it two different ways, and only one of them tolerates skipping
the index:

- `helm install`/`helm pull` against a direct `.tgz` URL works fine without an
  index. That is how the Argo CD chart itself was installed
  (`helm install argocd http://192.168.3.21:8888/helm/argo-cd-10.8.0.tgz ...`).
- Argo CD's own `Application.spec.sources[].repoURL` + `chart:` does not work
  this way. Its repo-server always treats `repoURL` as a repo root and
  appends `/index.yaml`, then resolves the chart by name inside it, the same
  resolution `helm repo add` + `helm search repo` would do. Point it at a
  direct `.tgz` URL and it 404s on
  `<url>/index.yaml` (confirmed, Part 7: Argo CD reported exactly this for
  both the Longhorn and victoria-metrics-k8s-stack Applications on first
  apply).

So: any chart an Argo CD `Application` will source needs a real entry in
`index.yaml`, not just the `.tgz` sitting in the directory. Steps:

1. `helm pull <chart> --repo <upstream>` (or `--version X --repo ...` for a
   pinned version) on blog-demo-vm.
2. `cp` the resulting `.tgz` into `/home/ubuntu/lab-mirror/helm/`.
3. Regenerate the index from that directory:
   ```bash
   cd /home/ubuntu/lab-mirror/helm && helm repo index . --url http://192.168.3.21:8888/helm/
   ```
   This rewrites `index.yaml` from every `.tgz` present, so it is safe to
   rerun after adding more charts later; it does not need per-chart flags.
4. In the Application manifest, set `repoURL` to the directory root
   (`http://192.168.3.21:8888/helm/`), not the chart's own filename, with
   `chart: <name>` and `targetRevision: <version>` doing the actual lookup.
5. Confirm the index served the new entry:
   `curl -s http://192.168.3.21:8888/helm/index.yaml | grep -A2 '^  <chart-name>:'`

Step 3 is the one that is easy to skip, since the chart already works if you
test it locally with `helm template <chart> <path-to-tgz>.tgz` or a manual
`helm pull` against the raw URL. Neither of those goes through
`Application.spec.sources`, so neither one would have caught the missing
index entry before Argo CD did.

## Rebuilding the mirror from scratch

```bash
V="v1.30.5+k3s1"; VE="v1.30.5%2Bk3s1"
BASE="https://github.com/k3s-io/k3s/releases/download/$VE"
mkdir -p "/home/ubuntu/lab-mirror/k3s/$V"
cd "/home/ubuntu/lab-mirror/k3s/$V"
for f in k3s sha256sum-amd64.txt k3s-airgap-images-amd64.tar.zst; do
    curl -sfL -o "$f" "$BASE/$f"
done
curl -sfL -o ../install.sh https://get.k3s.io
grep -E "  (k3s|k3s-airgap-images-amd64\.tar\.zst)$" sha256sum-amd64.txt | sha256sum -c -
```
