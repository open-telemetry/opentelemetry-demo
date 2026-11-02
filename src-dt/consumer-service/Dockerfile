FROM node:24.22.2-alpine AS build

WORKDIR /usr/src/app

COPY ["package*.json", "./"]

RUN npm ci --omit-dev

# -----------------------------------------------------------------------------

FROM node:24.22.2-alpine

RUN apk upgrade --no-cache

USER node
WORKDIR /usr/src/app/

COPY --chown=node:node --from=build ["/usr/src/app/node_modules/", "./node_modules/"]
COPY --chown=node:node ["src", "src"]

# Two variants ship per version. They differ only in whether the mock-malicious
# json-rules-engine-simplified package is loaded at runtime — it stays installed
# in node_modules either way, so only runtime detection tells them apart.
ARG VARIANT=vulnerable
RUN case "$VARIANT" in \
      vulnerable) ;; \
      healthy) \
        grep -q "^require('json-rules-engine-simplified');" src/index.js \
          || { echo "VARIANT=healthy: require line not found in src/index.js" >&2; exit 1; }; \
        sed -i "s|^require('json-rules-engine-simplified');|// require('json-rules-engine-simplified');|" src/index.js ;; \
      *) echo "Unknown VARIANT '$VARIANT', expected 'vulnerable' or 'healthy'" >&2; exit 1 ;; \
    esac

CMD [ "node", "src/index.js" ]
