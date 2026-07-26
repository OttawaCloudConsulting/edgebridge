# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Single-file HTTP bridge for SmartThings Edge drivers, which can only reach LAN addresses and cannot bind a stable port. Outbound: driver → `/api/forward?url=<URL>` → internet. Inbound: LAN device → server → hub IP:port a driver registered earlier. Runs on bare metal, in Docker, and in Kubernetes.

## Fork policy

OCC fork of `toddaustin07/edgebridge` (`upstream` remote). The fork **has diverged** — it carries k8s-readiness changes, a test suite, a container build, and CI. It is no longer a fast-forwardable mirror.

Syncing upstream is now a merge, and `edgebridge.py` is the file that will conflict:

```bash
git fetch upstream && git merge upstream/main
```

Work on `develop`; release by merging to `main` and tagging `v*`.

The generic fixes in our diff (log redaction, `passto_hub` timeout, `global FWTIMEOUT`, broad `RequestException` handling) are worth offering upstream to shrink the delta.

## Commands

```bash
pip install -r requirements-dev.txt
pytest                                    # 54 tests
pytest tests/test_server.py -k healthz     # single test
ruff check .

python3 edgebridge.py [-d] [--config PATH] [--state-dir PATH]

docker build -t edgebridge:dev .           # root context, not docker/
cd docker && docker-compose up -d --build
```

`edgebridge.exe`, `edgebridge4pi` and `edgebridge4pi64` are committed prebuilt binaries from upstream — nothing here rebuilds them, so Python edits don't reach them.

## Architecture (`edgebridge.py`)

All four verb handlers delegate to `proc_msg()`, which reads the body and routes:

1. `proc_registered_requests()` — matches **source IP** against `registrations`, relays via `passto_hub()`, stops. Matching is by IP, not endpoint, so a registered device's `/api/forward` calls get swallowed here.
2. Otherwise `handle_requests(server)` parses `/api/<forward|register>?...`.

`do_GET` checks `/healthz` and `/readyz` *before* step 1, so a probe from a registered source IP is never relayed to a hub.

`build_headers()` forwards every client header except `user-agent`/`host`/`te`/`connection`. The bearer token is injected only when the target is `api.smartthings.com` **and** the client sent no `Authorization`. Always log headers through `redact_headers()` — the token is in there.

`proc_forward()` takes everything after `url=` verbatim and dispatches via `getattr(requests, lc_method)` (GET/POST/PUT). Timeouts and any other `RequestException` both return 502.

`passto_hub()` builds `http://<hubaddr>/<devaddr>/<original-method><original-path>`. The driver parses that composite path — the shape is a contract, don't clean it up.

`error_proc()` drops all registrations for a hub after 3 consecutive send failures. Scrub messages are expected, not errors.

**Config and state are separate paths on purpose.** `--config` is read once at startup and may be read-only (a Secret mount); `--state-dir` holds `.registrations` and must be writable. Never reintroduce a shared `os.getcwd()` for both.

## Deployment constraints

Inbound routing depends on the client source IP surviving to the process. Behind a default k8s Service, kube-proxy SNATs it to a node IP and every device registration silently stops matching — hence `externalTrafficPolicy: Local` in `k8s/service.yaml`. Outbound forwarding keeps working, which makes this confusing to diagnose. `tests/test_registrations.py` pins the behaviour.

Leave `Server_IP` unset in containers; pointing it at a LoadBalancer address makes `bind()` fail. Keep `replicas: 1` — registrations are per-pod in-memory state.

The token reaches the process as a **mounted file**, never an image layer or env var. CI asserts no `edgebridge.cfg` exists inside the built image.

## Testing notes

`edgebridge.log` does not exist until `process_config()` runs — it is created as a side effect. The autouse `bootstrap` fixture in `tests/conftest.py` handles this; without it almost anything raises `NameError`.

`responses` patches `requests` globally, so live-server tests must `responses.add_passthru(live_server)` or the test client's own call gets intercepted.

## Quirks — verify before "fixing"

- `/api/ping` fast-paths **only in `do_POST`**. A GET ping 400s. `/healthz` exists because of this; the POST-only ping stays for driver compatibility.
- `do_DELETE` runs `proc_registered_requests()` first, so a DELETE from a registered source IP is relayed to the hub instead of reaching `/api/register`.
- `verify_addr()` returns tuples, `read_regs()` restores lists. After restart `find_reg()`'s `==` fails → re-registration duplicates instead of replacing. Pinned by a test.
- Module-level `LOGFILE` is shadowed by a local in `process_config()`.
- `VERSION` tracks upstream and is hand-maintained; OCC's semver lives in the image tag and OCI labels.
- Ruff ignores E402/E711/F541/E722 — all pre-existing upstream style. The pyflakes rules stay on.
