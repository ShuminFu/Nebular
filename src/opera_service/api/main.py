import uvicorn
from webapi import app
import sys

if __name__ == "__main__":
    port = 9000
    # 检查是否有命令行参数传入端口
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("无效的端口号，使用默认端口")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # 允许外部访问
        port=port,       # 设置端口
        reload=True      # 开发模式下启用热重载
    )