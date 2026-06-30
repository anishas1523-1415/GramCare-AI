FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Build the Next.js app
RUN npm run build

EXPOSE 3001

CMD ["npm", "start", "-p", "3001"]
