#!/bin/bash

# 确保在正确的目录中
cd "$(dirname "$0")" || exit

echo "拉取最新代码..."
git pull

echo "重启容器，应用最新代码..."
docker compose restart nebular

echo "更新完成，查看日志:"
docker compose logs -f nebular 