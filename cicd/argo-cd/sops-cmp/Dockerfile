# syntax=docker/dockerfile:1.7

# sthings-sops-cmp: Argo CD Config Management Plugin sidecar image.
# Mirrors the sthings-avp pattern: ships pinned sops + age + kustomize + helm,
# runs as UID 999 under /home/argocd, expects /var/run/argocd/argocd-cmp-server
# to be provided via the shared volume from the argocd-repo-server init container.
#
# Tag scheme: sops-age-kustomize-helm, e.g. 3.12.2-1.3.1-5.8.1-4.1.4
#
# Build via the stuttgart-things dagger/docker module:
#   task build-sops-cmp       # local build only
#   task push-sops-cmp        # build + push to ghcr.io (needs GITHUB_USER/GITHUB_TOKEN)
#
# Or directly with buildx:
#   docker buildx build \
#     --platform linux/amd64,linux/arm64 \
#     --build-arg SOPS_VERSION=3.12.2 \
#     --build-arg AGE_VERSION=1.3.1 \
#     --build-arg KUSTOMIZE_VERSION=5.8.1 \
#     --build-arg HELM_VERSION=4.1.4 \
#     -t ghcr.io/stuttgart-things/sthings-sops-cmp:3.12.2-1.3.1-5.8.1-4.1.4 \
#     --push .

ARG SOPS_VERSION=3.12.2
ARG AGE_VERSION=1.3.1
ARG KUSTOMIZE_VERSION=5.8.1
ARG HELM_VERSION=4.1.4

# ---------- Stage 1: download and verify tools ----------
FROM --platform=${BUILDPLATFORM} alpine:3.21 AS tools

ARG SOPS_VERSION
ARG AGE_VERSION
ARG KUSTOMIZE_VERSION
ARG HELM_VERSION
ARG TARGETARCH

RUN apk add --no-cache curl tar ca-certificates

WORKDIR /tmp/dl

# sops (static Go binary, released directly)
RUN curl -fsSL -o /usr/local/bin/sops \
      "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${TARGETARCH}" \
 && chmod +x /usr/local/bin/sops \
 && /usr/local/bin/sops --version

# age + age-keygen
RUN curl -fsSL -o age.tgz \
      "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-${TARGETARCH}.tar.gz" \
 && tar -xzf age.tgz \
 && mv age/age         /usr/local/bin/age \
 && mv age/age-keygen  /usr/local/bin/age-keygen \
 && chmod +x /usr/local/bin/age /usr/local/bin/age-keygen \
 && /usr/local/bin/age --version

# kustomize
RUN curl -fsSL -o kustomize.tgz \
      "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_${TARGETARCH}.tar.gz" \
 && tar -xzf kustomize.tgz \
 && mv kustomize /usr/local/bin/kustomize \
 && chmod +x /usr/local/bin/kustomize \
 && /usr/local/bin/kustomize version

# helm
RUN curl -fsSL -o helm.tgz \
      "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
 && tar -xzf helm.tgz \
 && mv "linux-${TARGETARCH}/helm" /usr/local/bin/helm \
 && chmod +x /usr/local/bin/helm \
 && /usr/local/bin/helm version --short

# ---------- Stage 2: final runtime image ----------
FROM alpine:3.21

ARG SOPS_VERSION
ARG AGE_VERSION
ARG KUSTOMIZE_VERSION
ARG HELM_VERSION

LABEL org.opencontainers.image.source="https://github.com/stuttgart-things/flux" \
      org.opencontainers.image.title="sthings-sops-cmp" \
      org.opencontainers.image.description="Argo CD CMP sidecar for SOPS-encrypted manifests" \
      org.opencontainers.image.licenses="Apache-2.0" \
      sops.version="${SOPS_VERSION}" \
      age.version="${AGE_VERSION}" \
      kustomize.version="${KUSTOMIZE_VERSION}" \
      helm.version="${HELM_VERSION}"

# bash: for `sh -c` generate scripts using process substitution if needed
# git: helm chart dependency fetch, Argo CD repo ops
# findutils: GNU `find` semantics for discover rules (alpine's busybox find is close but not identical)
#
# Note: UID 999 is pinned to match `runAsUser: 999` in the Argo CD repo-server
# sidecar. GID 999 is intentionally NOT pinned — alpine 3.21 ships a pre-existing
# `ping` group at GID 999, so we let addgroup auto-assign a free GID instead.
RUN apk add --no-cache bash ca-certificates findutils git \
 && addgroup -S argocd \
 && adduser  -u 999 -S -G argocd -h /home/argocd argocd \
 && mkdir -p /home/argocd/cmp-server/plugins \
             /home/argocd/cmp-server/config \
             /.config/sops/age \
 && chown -R argocd:argocd /home/argocd /.config

COPY --from=tools /usr/local/bin/sops        /usr/local/bin/sops
COPY --from=tools /usr/local/bin/age         /usr/local/bin/age
COPY --from=tools /usr/local/bin/age-keygen  /usr/local/bin/age-keygen
COPY --from=tools /usr/local/bin/kustomize   /usr/local/bin/kustomize
COPY --from=tools /usr/local/bin/helm        /usr/local/bin/helm

# SOPS resolves age keys from SOPS_AGE_KEY_FILE; release.yaml mounts the key
# into /.config/sops/age/keys.txt (read-only) to match the standard path.
ENV XDG_CONFIG_HOME=/.config \
    SOPS_AGE_KEY_FILE=/.config/sops/age/keys.txt

USER 999
WORKDIR /home/argocd

# The entrypoint is provided at runtime via the shared volume:
#   command: [/var/run/argocd/argocd-cmp-server]
# See cicd/argo-cd/release.yaml repoServer.extraContainers.
