import uvicorn
from webapi import app

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # 允许外部访问
        port=9000,       # 设置端口
        reload=True      # 开发模式下启用热重载
    )