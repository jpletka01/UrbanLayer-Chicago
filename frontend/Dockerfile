# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

ARG VITE_MAPBOX_TOKEN
ARG VITE_API_BASE=""
ARG VITE_SENTRY_DSN=""
ARG VITE_CLARITY_ID=""

ENV VITE_MAPBOX_TOKEN=${VITE_MAPBOX_TOKEN}
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
ENV VITE_CLARITY_ID=${VITE_CLARITY_ID}

COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

ARG NGINX_CONF=nginx.conf

COPY --from=builder /app/dist /usr/share/nginx/html
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
