FROM node:18-alpine AS build
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY ./package*.json ./
RUN npm install && npm ci
RUN apk add --no-cache libc6-compat protobuf-dev protoc
COPY . .
COPY ../../pb ./pb
RUN npm run grpc:generate
RUN npm run build

FROM node:18-alpine AS runner
RUN apk add --no-cache protobuf-dev protoc
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

COPY --from=build /app/next.config.js ./
COPY --from=build /app/utils/telemetry/Instrumentation.js ./
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

ENV PORT 8080
EXPOSE ${PORT}

ENTRYPOINT npm start
