# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Single-file HTTP bridge for SmartThings Edge drivers, which can only reach LAN addresses and cannot bind a stable port. Outbound: driver → `/api/forward?url=<URL>` → internet. Inbound: LAN device → server → hub IP:port a driver registered earlier.

## Fork policy

OCC fork of `toddaustin07/edgebridge` (`upstream` remote), maintained as a **clean mirror** — the fork's original `docker/` contribution was merged upstream and lives there now, so there are no fork-local commits. Sync with:

```bash
git fetch upstream && git merge --ff-only upstream/main
```

Keep it fast-forwardable: don't land fork-local patches on `develop`. Fixes go upstream as PRs. Work on `develop`, release to `main` via PR.

## Commands

```bash
python3 edgebridge.py [-d]     # -d dumps forwarded bodies/responses

# Docker (from docker/) — build context can't see parent dir:
cp ../edgebridge.py ../requirements.txt . && docker-compose up -d --build
```

No tests, linter, or build script. `edgebridge.exe`, `edgebridge4pi` (32-bit) and `edgebridge4pi64` are committed prebuilt binaries — nothing in the repo rebuilds them, so Python edits don't reach them.

## Architecture (`edgebridge.py`)

All four verb handlers (`do_GET`/`do_POST`/`do_PUT`/`do_DELETE`) delegate to `proc_msg()`, which reads the body and routes:

1. `proc_registered_requests()` — matches **source IP** against `registrations`, relays via `passto_hub()`, stops. Matching is by IP, not endpoint, so a registered device's `/api/forward` calls get swallowed here.
2. Otherwise `handle_requests(server)` parses `/api/<forward|register>?...`, taking method/path off the handler.

`build_headers()` forwards every client header except `user-agent`/`host`/`te`/`connection`, then overrides `Host`/`User-Agent`. The SmartThings bearer token is injected only when the target is `api.smartthings.com` **and** the client sent no `Authorization` of its own.

`proc_forward()` takes everything after `url=` verbatim (target URL may contain `&`/`?`) and dispatches via `getattr(requests, lc_method)` — GET/POST/PUT only.

`passto_hub()` builds `http://<hubaddr>/<devaddr>/<original-method><original-path>`. Driver parses that composite path — the shape is a contract, don't clean it up.

`error_proc()` drops all registrations for a hub after 3 consecutive send failures. Scrub messages in the log are expected, not errors.

`.registrations` (gitignored) is JSON-per-line, rewritten in full on every change. All paths are `os.getcwd()`-relative, so start the server from the config's directory. `Server_IP` in the config binds one interface; unset means all interfaces plus an auto-detect for the banner.

## Quirks — verify before "fixing"

- `/api/ping` fast-paths **only in `do_POST`**. A GET/PUT/DELETE ping falls through to `handle_requests()` and 400s (no `?` in the path).
- `do_DELETE` now runs `proc_registered_requests()` first, so a DELETE from a registered source IP is relayed to the hub instead of reaching `/api/register`.
- `FWTIMEOUT` assigned in `process_config()` without `global`, so `forwarding_timeout` config never applies; always 5s.
- `verify_addr()` returns tuples, `read_regs()` restores lists. After restart `find_reg()`'s `==` fails → re-registration duplicates instead of replacing.
- Module-level `LOGFILE` shadowed by a local in `process_config()`.
- `VERSION` is hand-maintained.
