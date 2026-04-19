FROM node:20-alpine AS deps
WORKDIR /repo
RUN corepack enable
COPY package.json yarn.lock .yarnrc.yml* ./
COPY .yarn .yarn
COPY apps/web/package.json apps/web/package.json
COPY apps/api/package.json apps/api/package.json
RUN yarn install --immutable

FROM node:20-alpine AS builder
WORKDIR /repo
RUN corepack enable
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/.yarn ./.yarn
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN yarn workspace ouroboros-web build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
COPY --from=builder /repo/apps/web/.next ./.next
COPY --from=builder /repo/apps/web/public ./public
COPY --from=builder /repo/apps/web/package.json ./package.json
COPY --from=builder /repo/node_modules ./node_modules
EXPOSE 3000
CMD ["yarn", "start"]
