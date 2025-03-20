FROM node:18-alpine
RUN apk update && \
    apk add --no-cache \
    pnpm \
    yarn \
    python3 \
    make \
    g++ \
    git \
    bash
# 设置工作目录
WORKDIR /app
