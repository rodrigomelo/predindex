FROM node:20-slim

WORKDIR /app

COPY package.json .
RUN npm install --production

COPY . .

EXPOSE 5001

CMD ["node", "src/index.js"]
