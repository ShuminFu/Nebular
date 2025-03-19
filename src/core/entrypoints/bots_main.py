import asyncio
import multiprocessing
import os
import base64
from dotenv import load_dotenv
from src.core.logger_config import get_logger, get_logger_with_trace_id
from src.core.crew_bots.crew_monitor import CrewMonitor
async def main():
    # 加载.env文件中的环境变量
    load_dotenv()

    # 获取logger实例
    log = get_logger(__name__, log_file="logs/main.log")
    log = get_logger_with_trace_id()

    # 仅在环境变量启用远程观测时初始化openlit
    enable_opentelemetry = os.environ.get("ENABLE_OPENTELEMETRY", "false").lower()
    if enable_opentelemetry in ("true", "1", "yes", "y"):
        log.info("OpenTelemetry已启用，初始化openlit")
        try:
            import openlit

            openlit.init()
            LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY")
            LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY")
            LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST")
            LANGFUSE_AUTH = base64.b64encode(f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()).decode()
            log.info(f"LANGFUSE_AUTH: {LANGFUSE_AUTH}")
            os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"
        except ImportError as e:
            log.error(f"OpenTelemetry初始化失败: {str(e)}")
            log.info("程序将继续运行，但没有遥测功能")
    else:
        log.info("OpenTelemetry未启用，跳过openlit初始化")

    try:
        # 创建并启动监控器
        monitor = CrewMonitor()
        await monitor.start()

        # 启动定期检查任务
        check_task = asyncio.create_task(
            monitor._periodic_check(
                monitor_interval=30,
                bot_interval=60,
            )
        )

        # 保持主程序运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        log.info("收到中断信号，正在停止...")
        # 取消定期检查任务
        check_task.cancel()
        # 停止监控器
        await monitor.stop()
        log.info("程序已停止")
    except Exception as e:
        log.error(f"程序运行出错: {str(e)}")
        # 取消定期检查任务
        if "check_task" in locals() and not check_task.done():
            check_task.cancel()
        # 停止监控器
        if "monitor" in locals():
            await monitor.stop()
        raise

if __name__ == "__main__":
    # 设置多进程启动方法
    multiprocessing.set_start_method('spawn')
    try:
        asyncio.run(main())
    except Exception as e:
        # 获取logger实例
        log = get_logger(__name__, log_file="logs/main.log")
        log.error(f"主程序异常退出: {str(e)}")