import asyncio
import multiprocessing
from src.core.logger_config import get_logger, get_logger_with_trace_id
from src.core.crew_bots.crew_monitor import CrewMonitor


async def main():
    # 获取logger实例
    # setup_logger(name="main")
    log = get_logger(__name__, log_file="logs/main.log")
    # 为main函数创建新的trace_id
    log = get_logger_with_trace_id()

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