FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# Keep the developer image on the same uv release used by CI. The project
# lockfile, rather than a mutable global installation, remains authoritative.
COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/
ENV UV_LINK_MODE=copy

# The upstream image includes an unused Yarn APT source with an expired key.
# This project uses npm; remove that source without weakening APT verification.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
	&& apt-get update \
	&& export DEBIAN_FRONTEND=noninteractive \
	&& apt-get install -y --no-install-recommends postgresql-client redis-tools \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*
