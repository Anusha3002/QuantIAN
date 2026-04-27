# Multi-stage build for the React/Vite dashboard.
# Stage 1: Node build -> static assets
# Stage 2: nginx that both serves the SPA and proxies /api/<svc> to peers.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# default proxy targets match docker-compose service names
ENV REGISTRY_URL=http://registry:8000 \
    AWS_INGESTION_URL=http://ingestion:8001 \
    AZURE_ANOMALY_URL=http://anomaly:8002 \
    GCP_RISK_URL=http://risk:8003 \
    IOT_BRIDGE_URL=http://iot-bridge:8004

EXPOSE 80
