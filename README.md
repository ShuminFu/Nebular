# Nebular

Nebular 是一个基于 Python 的 AI 助手实验平台，集成了多种现代 AI 工具和框架，用于探索和开发智能助手应用。

## 🌟 主要特性

- 基于 FastAPI 的现代 Web 服务架构
- 集成 AutoGen 框架进行 AI 代理开发
- 支持 CrewAI 进行多智能体协作
- 包含 FLAML AutoML 功能
- 实时通信支持（通过 SignalR）

## 🛠️ 技术栈

- Python 3.12
- FastAPI
- AutoGen
- CrewAI
- FLAML
- Uvicorn
- LoguRu

## 🚀 快速开始

### 前置要求

- Python 3.12
- Poetry（包管理工具）

### 安装

1. 克隆仓库：

```bash
git clone https://github.com/ShuminFu/Nebular.git
cd Nebular
```

2. 使用 Poetry 安装依赖：

```bash
poetry install
```

### 项目结构

```
Nebular/
├── ai_core/        # AI 核心功能实现
├── config/         # 配置文件
├── Design/         # 设计文档
├── Opera/          # 操作相关模块
├── playground/     # 实验和测试代码
└── src/           # 源代码主目录
```

## 📝 使用说明

项目使用 Poetry 进行依赖管理，主要功能模块位于 `src` 和 `ai_core` 目录。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

Copyright (c) 2024 Shumin Fu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

--- 