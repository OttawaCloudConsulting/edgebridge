# Kubernetes reference manifests

These are **reference only**. The deployed source of truth lives in the project repo alongside the real SealedSecret. Copy what you need.

## The one thing that will bite you

edgebridge routes inbound device messages by matching the **source IP** of the request against its registration table. Behind a default Service, kube-proxy SNATs inbound traffic to a node IP, so every device appears to come from the same address, nothing matches, and messages are dropped without an error.

`service.yaml` sets `externalTrafficPolicy: Local` to preserve the client IP. This is a correctness requirement, not tuning. If inbound device messages stop working, check this first.

Outbound forwarding (`/api/forward`) does not depend on source IP and will keep working regardless, which is what makes this failure mode confusing — half the product works.

## Configuration contract

| Item | Value |
|---|---|
| Config path | `/etc/edgebridge/edgebridge.cfg` (read-only mount) |
| State path | `/var/lib/edgebridge` (must be writable) |
| Liveness / readiness | `GET /healthz`, `GET /readyz` |
| Container port | 8088 (matches `Server_Port` in the config) |
| Runtime user | uid/gid 10001, non-root |

Leave **`Server_IP` unset** in the mounted config. Pointing it at the LoadBalancer address makes `bind()` fail, because the pod does not own that address. Unset binds all interfaces.

Keep `replicas: 1`. Registrations live in memory and in a per-pod `emptyDir`, and a device's message reaches whichever pod the Service picks — which may not be the one holding its registration.

## Secret rotation

Config is read once at startup, so a rotated Secret does not take effect on its own:

```sh
kubectl rollout restart deployment/edgebridge
```

The `checksum/config` pod annotation exists so a templating tool (Helm, Kustomize) can trigger this automatically.

The Secret is mounted as a **directory**, not with `subPath`. subPath mounts never receive updates when the Secret changes, which would silently pin you to the config that existed at pod start.

## Apply order

```sh
kubectl apply -f sealedsecret.yaml   # from the project repo, not the example here
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## Verifying

```sh
kubectl get pods -l app.kubernetes.io/name=edgebridge
kubectl logs -l app.kubernetes.io/name=edgebridge
```

The startup banner prints the version and listening address. To confirm outbound forwarding:

```sh
kubectl exec deploy/edgebridge -- python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8088/healthz').status)"
```

Inbound routing can only be verified with a real device: register a driver, have the LAN device send its message, and confirm it arrives. That is the check that catches a missing `externalTrafficPolicy: Local`.
