FROM node:18-alpine

# 设置工作目录
WORKDIR /app

# 复制Vue2项目到容器
COPY ./my-vue2-project /app/project

# 进入项目目录
WORKDIR /app/project

# 安装依赖
RUN yarn install || npm install

# 构建项目
RUN yarn build || npm run build

# 列出构建后的文件结构
RUN echo "==== Compiled File Structure ====" && \
    ls -la dist && \
    echo "\n==== Detailed File Listing ====" && \
    find dist -type f | sort && \
    echo "\n==== File Sizes ====" && \
    du -h dist/* | sort -hr

# 输出构建结果
CMD ["sh", "-c", "echo 'Build completed. Files are available in /app/project/dist' && ls -la dist"] 