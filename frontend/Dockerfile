FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM deps AS build
ARG VITE_APP_CLIENT_ID
ARG VITE_API_BASE_URL=
ARG VITE_TENANT_ID
ARG VITE_LOCAL_MODE
ARG BACKEND_URL=http://backend:8000
ENV VITE_APP_CLIENT_ID=$VITE_APP_CLIENT_ID
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_TENANT_ID=$VITE_TENANT_ID
ENV VITE_LOCAL_MODE=$VITE_LOCAL_MODE
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS prod
ARG BACKEND_URL=http://backend:8000
RUN apk add --no-cache ca-certificates
ENV BACKEND_URL=$BACKEND_URL
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
