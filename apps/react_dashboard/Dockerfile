# Build Stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Production Stage - Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80 (nginx default)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
