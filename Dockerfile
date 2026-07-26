# Build context is the repository root, so the config file is never part of the
# image. The SmartThings bearer token is supplied at runtime by mounting a
# config file at /etc/edgebridge/edgebridge.cfg (a Kubernetes Secret volume, or
# a bind mount under Docker). Baking it into a layer would make it recoverable
# by anyone who can pull the image.

ARG PYTHON_IMAGE=python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

FROM ${PYTHON_IMAGE} AS build

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM ${PYTHON_IMAGE}

ARG VERSION=0.0.0-dev
ARG REVISION=unknown

LABEL org.opencontainers.image.title="edgebridge" \
      org.opencontainers.image.description="Forwarding bridge server for SmartThings Edge drivers" \
      org.opencontainers.image.source="https://github.com/OttawaCloudConsulting/edgebridge" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    # Only used by HEALTHCHECK below. Override it to match Server_Port if the
    # mounted config does not use the default, or the container reports
    # unhealthy while serving normally.
    EDGEBRIDGE_HEALTH_PORT=8088

COPY --from=build /opt/venv /opt/venv
COPY edgebridge.py /app/edgebridge.py

# Config is mounted read-only here; state must be writable, so they are
# separate directories. Both are owned by the runtime user so that
# readOnlyRootFilesystem with an emptyDir at /var/lib/edgebridge works.
RUN mkdir -p /etc/edgebridge /var/lib/edgebridge \
 && chown -R 10001:10001 /var/lib/edgebridge

USER 10001:10001
WORKDIR /var/lib/edgebridge
EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import os,sys,urllib.request; p=os.environ.get('EDGEBRIDGE_HEALTH_PORT','8088'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["python", "/app/edgebridge.py", \
            "--config", "/etc/edgebridge/edgebridge.cfg", \
            "--state-dir", "/var/lib/edgebridge"]
