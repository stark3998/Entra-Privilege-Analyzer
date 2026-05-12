# frontend/Dockerfile
# Pinned base images for reproducible builds
FROM node:20-alpine@sha256:10746ef6fe9b2bfab0ee1c5b13a0d80e4b8dbe4e5799f5f60e8e3300ca07beab AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM deps AS build
COPY . .
RUN npm run build

FROM nginx:alpine@sha256:a5127daff3d6f4f57468f798a81f799c2e8f9a9e5b7f2c9b1a3f4b7e6e7e1a2 AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
