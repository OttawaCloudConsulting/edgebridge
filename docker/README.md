# EdgeBridge Docker Support

## Overview

Running edgebridge in a container keeps it alive across reboots without a systemd unit.

The image is built from the `Dockerfile` **in the repository root**. Earlier versions kept a second Dockerfile in this directory, which forced you to copy `edgebridge.py` and `requirements.txt` up into `docker/` before every build. That is no longer necessary — the compose file sets the build context to the repository root.

## Configuration

Your SmartThings bearer token is **never built into the image**. It is supplied at runtime by mounting a config file at `/etc/edgebridge/edgebridge.cfg`.

```sh
cp edgebridge.cfg.example edgebridge.cfg
# edit edgebridge.cfg and add your token
```

`docker/edgebridge.cfg` is gitignored, so the filled-in copy cannot be committed by accident. Only `edgebridge.cfg.example`, which contains placeholders, is tracked.

## Running

From this directory:

```sh
docker-compose up -d --build
```

Update the compose file with your subnet, gateway, DNS server, and the LAN IP address you want edgebridge to answer on. A static address matters because Edge drivers register a fixed edgebridge address.

Test it by listing your SmartThings devices through the bridge:

```sh
curl "http://192.168.1.88:8088/api/forward?url=https://api.smartthings.com/v1/devices"
```

The [`jq`](https://stedolan.github.io/jq/) tool is useful for reading the JSON that comes back.

## Health check

The image defines a `HEALTHCHECK` against `GET /healthz`. It probes port 8088 by default; if your config sets a different `Server_Port`, set `EDGEBRIDGE_HEALTH_PORT` to match or the container will report unhealthy while serving normally.

## Container details

- Runs as non-root (uid 10001)
- Config is read from `/etc/edgebridge/edgebridge.cfg` (mount read-only)
- The `.registrations` state file is written to `/var/lib/edgebridge`, which must be writable — use a volume or tmpfs if you run with `--read-only`
- Handles `SIGTERM`, so `docker stop` returns immediately instead of waiting out the grace period

## Kubernetes

See [`k8s/`](../k8s/) for reference manifests, including the Service settings needed to preserve client source IPs.
