# === Build stage ===
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./

RUN npm install --legacy-peer-deps --no-audit --no-fund 2>/dev/null || npm ci --no-audit --no-fund

COPY . .

RUN npm run build

# === Production stage ===
FROM node:20-alpine AS production

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

# Copy built app + deps from builder (deps cached in layer)
COPY --from=builder /app/build/ build/
COPY --from=builder /app/.svelte-kit/ .svelte-kit/
COPY --from=builder /app/node_modules/ node_modules/
COPY --from=builder /app/package.json ./

EXPOSE 3000

CMD ["node", "build/index.js"]
