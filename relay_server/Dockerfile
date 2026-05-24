FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY server.js chat.html ./
EXPOSE 9527
CMD ["node", "server.js"]