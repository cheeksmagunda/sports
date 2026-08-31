FROM mcr.microsoft.com/devcontainers/python:3.12

# Keep the developer image on the same uv release used by CI. The project
# lockfile, rather than a mutable global installation, remains authoritative.
COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/
ENV UV_LINK_MODE=copy

RUN apt-get update \
	&& export DEBIAN_FRONTEND=noninteractive \
	&& apt-get install -y --no-install-recommends postgresql-client redis-tools \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*
