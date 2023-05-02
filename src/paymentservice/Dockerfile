# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM node:16-alpine AS build

WORKDIR /usr/src/app/

COPY ./src/paymentservice/package*.json ./

RUN apk add --no-cache python3 make g++ && npm ci --omit=dev
RUN npm install --save @instana/collector

# -----------------------------------------------------------------------------

FROM node:16-alpine

USER node
WORKDIR /usr/src/app/
ENV NODE_ENV production

COPY --chown=node:node --from=build /usr/src/app/node_modules/ ./node_modules/
COPY ./src/paymentservice/ ./
COPY ./pb/demo.proto ./

ENV NODE_OPTIONS="--require ./node_modules/@instana/collector/src/immediate"

EXPOSE ${PAYMENT_SERVICE_PORT}
ENTRYPOINT [ "npm", "run", "start" ]
