# Build Stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

# VITE_* variables are BUILD-time (inlined into the bundle by Vite).
# Passing them as runtime `environment:` in docker-compose has no effect on
# an already-built bundle — they must arrive here as build args.
#
# Defaults to production, not localhost: this ENV takes precedence over
# .env.production in Vite, so a localhost default silently shipped a bundle
# pointing at localhost:8000 for any build that didn't pass the arg — a
# portal that loads fine and then fails every request. docker-compose.yml
# passes the localhost URL explicitly for local runs.
ARG VITE_API_URL=https://gramcare-fastapi.onrender.com/api/v1
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Production Stage - Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80 (nginx default)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
