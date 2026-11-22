# Stage 1: Build
FROM node:24-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

ARG VITE_API_BASE=""
ARG VITE_SENTRY_DSN=""
ARG VITE_CLARITY_ID=""
ARG VITE_SENTRY_ENVIRONMENT=""
ARG VITE_SENTRY_RELEASE=""
# Where the source maps go (vite.config.ts). Not secret; the auth token below is.
ARG SENTRY_ORG=""
ARG SENTRY_PROJECT=""
ARG SENTRY_URL=""

ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
ENV VITE_CLARITY_ID=${VITE_CLARITY_ID}
ENV VITE_SENTRY_ENVIRONMENT=${VITE_SENTRY_ENVIRONMENT}
ENV VITE_SENTRY_RELEASE=${VITE_SENTRY_RELEASE}

COPY . .
# The Sentry token arrives as a BuildKit secret (docker-compose.prod.yml), so it never lands in an
# image layer. Empty or absent = no source maps, the same build as before.
RUN --mount=type=secret,id=sentry_auth_token \
    SENTRY_AUTH_TOKEN="$(cat /run/secrets/sentry_auth_token 2>/dev/null || true)" \
    SENTRY_ORG="${SENTRY_ORG}" SENTRY_PROJECT="${SENTRY_PROJECT}" SENTRY_URL="${SENTRY_URL}" \
    npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

ARG NGINX_CONF=nginx.conf

COPY --from=builder /app/dist /usr/share/nginx/html
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
