# Frontend image: Vite build served by nginx, which also proxies /api and /ws
# to the backend container so the dashboard is served from one origin.
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes VITE_* values in at build time, so they are build args, not
# runtime env vars. Defaults match docker-compose.yml (dashboard on :8080).
ARG VITE_API_BASE_URL=""
ARG VITE_WS_URL="ws://localhost:8080/ws/simulation"
ARG VITE_SHADOW_WS_URL="ws://localhost:8080/ws/simulation/shadow"
ARG VITE_VISION_WS_URL="ws://localhost:8080/ws/vision"
ARG VITE_ANALYTICS_WS_URL="ws://localhost:8080/ws/analytics"
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_WS_URL=$VITE_WS_URL \
    VITE_SHADOW_WS_URL=$VITE_SHADOW_WS_URL \
    VITE_VISION_WS_URL=$VITE_VISION_WS_URL \
    VITE_ANALYTICS_WS_URL=$VITE_ANALYTICS_WS_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
