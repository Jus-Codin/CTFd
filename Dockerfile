FROM ghcr.io/astral-sh/uv:0.4.20 AS uv
FROM python:3.11-slim-bookworm AS build

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends --no-install-suggests \
        build-essential \
        libffi-dev \
        libssl-dev \
        git

COPY --from=uv /uv /usr/local/bin/uv

# - Silence uv complaining about not being able to use hard links,
# - tell uv to byte-compile packages for faster application startups,
# - prevent uv from accidentally downloading isolated Python builds,
# - pick a Python,
# - and finally declare `/opt/venv` as the target for `uv sync`.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.11 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml /_lock/
COPY uv.lock /_lock/
COPY CTFd/plugins /plugins/

# Synchronize DEPENDENCIES without the application itself.
# This layer is cached until uv.lock or pyproject.toml change.
# hadolint ignore=DL3003
RUN --mount=type=cache,target=/root/.cache \
    cd /_lock \
    && uv sync \
        --locked \
        --no-dev \
        --no-install-project \
    && for d in /plugins/*; do \
        if [ -f "$d/requirements.txt" ]; then \
            uv pip install \
                --python=${UV_PROJECT_ENVIRONMENT} \
                --no-deps \
                -r \
                "$d/requirements.txt"; \
        fi; \
    done


FROM python:3.11-slim-bookworm AS release
WORKDIR /opt/CTFd

ENV PATH="/opt/venv/bin:$PATH"

ENTRYPOINT [ "/opt/CTFd/docker-entrypoint.sh" ]
STOPSIGNAL SIGINT

RUN useradd \
    --no-log-init \
    --shell /bin/bash \
    -u 10001 \
    ctfd \
    && mkdir -p /var/log/CTFd /var/uploads

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends --no-install-suggests \
        libffi8 \
        libssl3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY --from=build --chown=10001:10001 /opt/venv /opt/venv

COPY --chown=10001:10001 . /opt/CTFd

RUN chown -R 10001:10001 /var/log/CTFd /var/uploads /opt/CTFd \
    && chmod +x /opt/CTFd/docker-entrypoint.sh

USER 10001
EXPOSE 8000
