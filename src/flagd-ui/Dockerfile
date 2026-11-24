# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Find eligible builder and runner images on Docker Hub. We use Ubuntu/Debian
# instead of Alpine to avoid DNS resolution issues in production.
#
# https://hub.docker.com/r/hexpm/elixir/tags?name=ubuntu
# https://hub.docker.com/_/ubuntu/tags
#
# This file is based on these images:
#
#   - https://hub.docker.com/r/hexpm/elixir/tags - for the build image
#   - https://hub.docker.com/_/debian/tags?name=bookworm-20250610-slim - for the release image
#   - https://pkgs.org/ - resource for finding needed packages
#   - Ex: docker.io/hexpm/elixir:1.20.1-erlang-28.5-debian-trixie-20260610-slim
#
FROM docker.io/hexpm/elixir:1.20.5-erlang-29.1.2-debian-trixie-20261123-slim@sha256:eed78763a32f23b30c53ac45f3a8f21a63f7d87924be14e1fdbff6f295b7f327 AS base

# install build dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential git \
  && rm -rf /var/lib/apt/lists/*

# prepare build dir
WORKDIR /app

# install hex + rebar
RUN mix local.hex --force \
  && mix local.rebar --force

FROM base AS test

# set test ENV
ENV MIX_ENV="test"

COPY ./src/flagd-ui/mix.exs ./src/flagd-ui/mix.lock ./
RUN mix deps.get --only $MIX_ENV

COPY ./src/flagd/demo.flagd.json ../flagd/demo.flagd.json
COPY ./src/flagd-ui/config config
COPY ./src/flagd-ui/priv priv
COPY ./src/flagd-ui/lib lib
COPY ./src/flagd-ui/test test

RUN mix test \
  && touch /tmp/flagd-ui-tests-passed

FROM base AS builder

# set build ENV
ENV MIX_ENV="prod"

# BuildKit skips unused stages, so depend on the test marker to require tests before building the release.
COPY --from=test /tmp/flagd-ui-tests-passed /tmp/flagd-ui-tests-passed

# install mix dependencies
COPY ./src/flagd-ui/mix.exs ./src/flagd-ui/mix.lock ./
RUN mix deps.get --only $MIX_ENV
RUN mkdir config

# copy compile-time config files before we compile dependencies
# to ensure any relevant config change will trigger the dependencies
# to be re-compiled.
COPY ./src/flagd-ui/config/config.exs ./src/flagd-ui/config/${MIX_ENV}.exs ./src/flagd-ui/config/runtime.exs config/
RUN mix deps.compile

RUN mix assets.setup

COPY ./src/flagd-ui/priv priv

COPY ./src/flagd-ui/lib lib

COPY ./src/flagd-ui/assets assets

# compile assets
RUN mix assets.deploy

# Compile the release
RUN mix compile

COPY ./src/flagd-ui/rel rel
RUN mix release

# start a new build stage so that the final image will only contain
# the compiled release and other runtime necessities
FROM docker.io/debian:trixie-20261123-slim@sha256:8aa5a7bf5a1955bddbe7d74fcdd0b91ab30e74362a8b73af672b0481b35b44a0 AS final

RUN apt-get update \
  && apt-get install -y --no-install-recommends libstdc++6 openssl locales ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Set the locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
  && locale-gen

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

WORKDIR "/app"
RUN chown nobody /app

# set runner ENV
ENV MIX_ENV="prod"

# Only copy the final release from the build stage
COPY --from=builder --chown=nobody:root /app/_build/${MIX_ENV}/rel/flagd_ui ./

ARG FLAGD_UI_PORT=4000
EXPOSE ${FLAGD_UI_PORT}

# If using an environment that doesn't automatically reap zombie processes, it is
# advised to add an init process such as tini via `apt-get install`
# above and adding an entrypoint. See https://github.com/krallin/tini for details
# ENTRYPOINT ["/tini", "--"]

CMD ["sh", "-c", "ulimit -n 65536 && exec /app/bin/server"]
