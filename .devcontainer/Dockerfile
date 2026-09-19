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
	&& apt-get install -y --no-install-recommends postgresql-client redis-tools git-lfs \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

# Railway CLI, pinned by version and checksum. It is a consumer of the
# Codespaces secret RAILWAY_API_TOKEN (workspace token) injected into login
# shells; nobody runs `railway login` in the container, so no session file
# and no second credential home (issue #235). Lets T-40 readiness checks
# (`railway volume list`, `railway logs`) run from the Codespace, not only
# from the operator Mac.
ARG RAILWAY_CLI_VERSION=5.57.10
RUN set -eu; \
	case "$(dpkg --print-architecture)" in \
		amd64) target=x86_64-unknown-linux-musl; sha=c883988b1fd0083af51881fe4c9d7d6ebb1882bccd4ee664738f7f9d078d5471 ;; \
		arm64) target=aarch64-unknown-linux-musl; sha=b686a82152b21e92ba709d0eb508c7b66749bf6e59488b8d593a7e09d6eede79 ;; \
		*) echo "unsupported architecture for the Railway CLI" >&2; exit 1 ;; \
	esac; \
	curl -fsSL -o /tmp/railway.tgz \
		"https://github.com/railwayapp/cli/releases/download/v${RAILWAY_CLI_VERSION}/railway-v${RAILWAY_CLI_VERSION}-${target}.tar.gz"; \
	echo "${sha}  /tmp/railway.tgz" | sha256sum -c -; \
	tar -xzf /tmp/railway.tgz -C /usr/local/bin railway; \
	chmod 0755 /usr/local/bin/railway; \
	rm -f /tmp/railway.tgz; \
	railway --version
