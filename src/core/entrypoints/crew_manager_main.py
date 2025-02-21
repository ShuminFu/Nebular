import asyncio
import multiprocessing
from uuid import UUID
from src.core.logger_config import get_logger, get_logger_with_trace_id, setup_logger
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool, BotForCreation, BotForUpdate
from src.core.crew_process import CrewManager, CrewRunner
from src.core.parser.api_response_parser import ApiResponseParser
from src.crewai_ext.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool

from typing import Optional
import backoff
import json



# 重试装饰器


@backoff.on_exception(backoff.expo,
                      (asyncio.TimeoutError, ConnectionError),
                      max_tries=3,
                      max_time=300)
async def run_crew_manager(bot_id: str):
    """为单个Bot运行CrewManager"""
    # 为每个manager实例创建新的trace_id
    log = get_logger_with_trace_id()
    manager = CrewManager()
    manager.bot_id = UUID(bot_id)
    bot_tool = BotTool()
    crew_processes = []
    parser = ApiResponseParser()

    try:
        # 1. 获取Bot信息和关联的Opera
        bot_info = bot_tool.run(action="get", bot_id=bot_id)
        _, bot_data = parser.parse_response(bot_info)
        log.info(f"获取Bot {bot_id} 信息: {bot_data}")

        # 获取所有关联的Opera
        staffs_result = bot_tool.run(
            action="get_all_staffs", bot_id=bot_id, data={"need_opera_info": True, "need_staffs": 1, "need_staff_invitations": 0}
        )
        _, staffs_data = parser.parse_response(staffs_result)
        managed_operas = [
            {
                "id": opera["operaId"],
                "name": opera.get("operaName", ""),
                "parent_id": opera.get("operaParentId"),
                "staff_id": [staff["id"] for staff in opera.get("staffs", [])],
            }
            for opera in staffs_data
            if opera.get("staffs")
        ]
        log.info(f"Bot {bot_id} 管理的Opera: {managed_operas}")

        # 2. 获取现有ChildBots及其管理的Opera
        default_tags = parser.parse_default_tags(bot_data)
        existing_child_bots = parser.get_child_bots(default_tags) or []
        log.info(f"现有ChildBots: {existing_child_bots}")

        # 获取ChildBots管理的Opera
        childbot_related_opera_ids = set()
        for child_bot_id in existing_child_bots:
            try:
                child_bot_info = bot_tool.run(action="get", bot_id=child_bot_id)
                _, child_data = parser.parse_response(child_bot_info)
                child_tags = parser.parse_default_tags(child_data)
                if child_tags and "related_operas" in child_tags:
                    childbot_related_opera_ids.update(child_tags["related_operas"])
                else:
                    # 与CrewManager相同的获取逻辑
                    staffs_result = bot_tool.run(
                        action="get_all_staffs",
                        bot_id=child_bot_id,
                        data={"need_opera_info": True, "need_staffs": 1, "need_staff_invitations": 0},
                    )
                    _, staffs_data = parser.parse_response(staffs_result)
                    child_operas = [str(opera["operaId"]) for opera in staffs_data if opera.get("staffs")]
                    childbot_related_opera_ids.update(child_operas)
                    log.warning(f"ChildBot {child_bot_id} 缺少managed_operas标签，已通过API获取到 {len(child_operas)} 个opera")
            except Exception as e:
                log.error(f"获取ChildBot {child_bot_id} 信息失败: {str(e)}")

        # 3. 为未覆盖的Opera创建ChildBot
        staff_invitation_tool = StaffInvitationTool()
        for opera in managed_operas:
            if str(opera["id"]) not in childbot_related_opera_ids:
                try:
                    # TODO 这里考虑先获取CR的配置，并且根据CR的配置来创建多个新的ChildBot
                    bot_config = BotForCreation(
                        name=f"CR-{opera['name']}",
                        description=f"管理Opera {opera['name']} 的自动Bot",
                        default_tags=json.dumps({
                            "related_operas": [str(opera["id"])],
                            "parent_bot": bot_id,
                        }),
                    )
                    create_result = bot_tool.run(action="create", data=bot_config)
                    _, new_bot = parser.parse_response(create_result)

                    # 发送Staff邀请
                    invitation_result = staff_invitation_tool.run(
                        action="create",
                        opera_id=opera["id"],
                        data={
                            "bot_id": new_bot["id"],
                            "roles": "auto_manager",
                            "permissions": "full_access",
                            "parameter": json.dumps({
                                "management_scope": {"opera_id": str(opera["id"]), "inherited_from": bot_id}
                            }),
                        },
                    )

                    # 更新CM的managed_bots列表
                    existing_child_bots.append(new_bot["id"])
                    # TODO 这里还要确保不会覆盖掉其他的字段
                    update_data = BotForUpdate(
                        is_default_tags_updated=True, default_tags=json.dumps({"childBots": existing_child_bots})
                    )
                    bot_tool.run(action="update", bot_id=bot_id, data=update_data)

                    log.info(f"为Opera {opera['id']} 创建了新的ChildBot: {new_bot['id']}")
                except Exception as e:
                    log.error(f"为Opera {opera['id']} 创建ChildBot失败: {str(e)}")

        # 4. 启动未激活的ChildBots
        for child_bot_id in existing_child_bots:
            try:
                # 获取子Bot状态
                child_bot_info = bot_tool.run(action="get", bot_id=child_bot_id)
                _, child_bot_data = parser.parse_response(child_bot_info)

                if not child_bot_data.get("isActive", True):
                    # 为未激活的子Bot创建CrewRunner进程
                    process = multiprocessing.Process(
                        target=start_crew_runner_process,
                        args=(
                            child_bot_id,
                            bot_id,
                            # TODO 这里添加从childbot中获取的动态配置并且传入
                        ),  # 传递当前manager的bot_id作为parent_bot_id
                    )
                    process.start()
                    crew_processes.append(process)
                    log.info(f"已为子Bot {child_bot_id} 启动CrewRunner进程，父Bot ID: {bot_id}")
            except Exception as e:
                log.error(f"处理子Bot {child_bot_id} 时出错: {str(e)}")
                continue

        # 运行CrewManager
        await manager.run()

    except asyncio.TimeoutError:
        log.error(f"Bot {bot_id} 等待连接超时，将进行重试")
        raise
    except KeyboardInterrupt:
        await manager.stop()
        for process in crew_processes:
            process.terminate()
            process.join()
        log.info(f"CrewManager和所有CrewRunner已停止，Bot ID: {bot_id}")
    except Exception as e:
        log.error(f"CrewManager运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        for process in crew_processes:
            process.terminate()
            process.join()
        raise


@backoff.on_exception(backoff.expo,
                      (asyncio.TimeoutError, ConnectionError),
                      max_tries=3,
                      max_time=300)
async def run_crew_runner(runner: CrewRunner, bot_id: str):
    """在新进程中运行CrewRunner"""
    # 为每个runner实例创建新的trace_id
    log = get_logger_with_trace_id()
    try:
        await runner.run()
    except Exception as e:
        log.error(f"CrewRunner运行出错，Bot ID: {bot_id}, 错误: {str(e)}")
        raise


def start_crew_runner_process(bot_id: str, parent_bot_id: str, crew_config: Optional[dict] = None):
    """在新进程中启动CrewRunner"""
    runner = CrewRunner(
        bot_id=UUID(bot_id),
        parent_bot_id=UUID(parent_bot_id),
        crew_config=crew_config,  # 传递动态配置
    )
    asyncio.run(run_crew_runner(runner, bot_id))

def start_crew_manager_process(bot_id: str):
    """在新进程中启动CrewManager"""
    asyncio.run(run_crew_manager(bot_id))

async def main():
    # 获取logger实例
    setup_logger(name="main")
    log = get_logger(__name__, log_file="logs/main.log")
    # 为main函数创建新的trace_id
    log = get_logger_with_trace_id()
    # 创建BotTool实例
    bot_tool = BotTool()
    parser = ApiResponseParser()

    # 获取所有Bot
    result = bot_tool.run(action="get_all")
    log.info(f"获取所有Bot结果: {result}")

    # 存储所有进程的列表
    processes = []

    try:
        status_code, bots_data = parser.parse_response(result)

        if status_code == 200:
            # 过滤符合条件的Bot
            crew_manager_bots = [
                bot for bot in bots_data
                if "测试" in bot["name"] and not bot["isActive"]
            ]
            # TODO: 这里可以把tag也加入到CrewManager的初始化信息中。
            log.info("符合条件的Bot列表:")
            for bot in crew_manager_bots:
                log.info(f"ID: {bot['id']}, Name: {bot['name']}, Description: {bot['description']}")

                # 为每个Bot创建新进程
                process = multiprocessing.Process(
                    target=start_crew_manager_process,
                    args=(bot['id'],)
                )
                process.start()
                processes.append(process)
                log.info(f"已为Bot {bot['id']}启动CrewManager进程")

            # 等待所有进程
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                log.info("正在停止所有进程...")
                for process in processes:
                    process.terminate()
                    process.join()
                log.info("所有进程已停止")
        else:
            log.error(f"API请求失败，状态码: {status_code}")
    except Exception as e:
        log.error(f"处理结果时出错: {str(e)}")
        # 确保清理所有进程
        for process in processes:
            process.terminate()
            process.join()

if __name__ == "__main__":
    # 设置多进程启动方法
    multiprocessing.set_start_method('spawn')
    asyncio.run(main())