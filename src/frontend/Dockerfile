FROM node:16-alpine AS deps
RUN apk add --no-cache libc6-compat

WORKDIR /app

COPY ./src/frontend/package*.json ./
RUN npm ci

FROM node:16-alpine AS builder
RUN apk add --no-cache libc6-compat protoc
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY ./pb ./pb
COPY ./src/frontend .

RUN npm run grpc:generate
RUN npm run build

FROM ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-nodejs:0.31.0 as instrumentation

FROM node:16-alpine AS runner
WORKDIR /app
RUN apk add --no-cache protoc

ENV NODE_ENV=production

RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Use deps from AutoInstrumentation
COPY --from=instrumentation --chown=nextjs:nodejs /autoinstrumentation/. /otel-auto-instrumentation
# Customize instrumentation
COPY --from=builder --chown=nextjs:nodejs /app/utils/opentelemetry.js /otel-auto-instrumentation/autoinstrumentation.js
ENV NODE_OPTIONS=" --require /otel-auto-instrumentation/autoinstrumentation.js"

USER nextjs

ENV PORT 8080
EXPOSE ${PORT}

CMD ["node", "server.js"]
