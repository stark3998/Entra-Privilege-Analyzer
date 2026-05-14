FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM deps AS build
ARG VITE_APP_CLIENT_ID
ARG VITE_API_BASE_URL
ARG VITE_TENANT_ID
ENV VITE_APP_CLIENT_ID=$VITE_APP_CLIENT_ID
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_TENANT_ID=$VITE_TENANT_ID
COPY . .
RUN npm run build

FROM node:20-alpine AS prod
RUN npm install -g serve
COPY --from=build /app/dist /app/dist
EXPOSE 80
CMD ["serve", "-s", "/app/dist", "-l", "80"]
