from typing import List, Set
import json
from src.crewai_ext.tools.opera_api.bot_api_tool import BotTool, BotForCreation, BotForUpdate
from src.crewai_ext.tools.opera_api.staff_invitation_api_tool import StaffInvitationTool
from src.core.parser.api_response_parser import ApiResponseParser
from src.crewai_ext.flows.manager_init_flow import ManagerInitFlow
from uuid import UUID


async def fetch_bot_data(bot_tool: BotTool, bot_id: str, log) -> dict:
    """获取Bot信息并解析响应"""
    bot_info = bot_tool.run(action="get", bot_id=bot_id)
    parser = ApiResponseParser()
    _, bot_data = parser.parse_response(bot_info)
    log.info(f"获取Bot {bot_id} 信息: {bot_data}")
    return bot_data


async def fetch_staff_data(bot_tool: BotTool, bot_id: str, log) -> List[dict]:
    """获取Bot关联的Opera信息"""
    parser = ApiResponseParser()
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
    return managed_operas


async def create_child_bot(bot_tool: BotTool, opera: dict, parent_bot_id: str, log) -> List[str]:
    """创建ChildBot并发送Staff邀请，同时生成CR配置。每个配置创建一个ChildBot。

    Args:
        bot_tool: BotTool实例
        opera: Opera信息字典，包含id、name等字段
        parent_bot_id: 父Bot的ID
        log: 日志记录器

    Returns:
        List[str]: 成功创建的ChildBot ID列表
    """
    try:
        parser = ApiResponseParser()
        staff_invitation_tool = StaffInvitationTool()
        created_bot_ids = []

        # 初始化ManagerInitFlow并生成配置
        flow = ManagerInitFlow(query=f"为Opera {opera['name']} 生成CR配置，Opera描述：{opera.get('description', '')}")
        config_result = await flow.kickoff_async()

        # 为每个配置创建一个ChildBot
        for i, runner_config in enumerate(config_result.get("runners", [])):
            # 创建Bot配置，包含CR配置
            bot_config = BotForCreation(
                name=f"CR-{opera['name']}-{i + 1}",  # 添加序号以区分不同的CR
                description=f"管理Opera {opera['name']} 的自动Bot #{i + 1}",
                default_tags=json.dumps({
                    "related_operas": [str(opera["id"])],
                    "parent_bot": parent_bot_id,
                    "crew_config": runner_config,  # 存储单个runner的配置
                }),
            )
            create_result = bot_tool.run(action="create", data=bot_config)
            _, new_bot = parser.parse_response(create_result)

            # 发送Staff邀请
            staff_invitation_tool.run(
                action="create",
                opera_id=opera["id"],
                data={
                    "bot_id": new_bot["id"],
                    "roles": "auto_manager",
                    "permissions": "full_access",
                    "parameter": json.dumps({
                        "management_scope": {
                            "opera_id": str(opera["id"]),
                            "inherited_from": parent_bot_id,
                            "cr_index": i,  # 记录CR的序号
                        }
                    }),
                },
            )

            created_bot_ids.append(new_bot["id"])
            log.info(f"为Opera {opera['id']} 创建了新的ChildBot {i + 1}: {new_bot['id']}")

        return created_bot_ids
    except Exception as e:
        log.error(f"为Opera {opera['id']} 创建ChildBot失败: {str(e)}")
        return []


async def update_parent_bot_tags(bot_tool: BotTool, bot_id: str, child_bots: list, log) -> None:
    """更新父Bot的managed_bots列表，保留其他default_tags字段"""
    try:
        # 获取当前bot的信息
        parser = ApiResponseParser()
        current_bot_data = await fetch_bot_data(bot_tool, bot_id, log)

        # 解析现有的default_tags
        current_tags = {}
        try:
            current_tags = parser.parse_default_tags(current_bot_data) or {}
        except Exception as e:
            log.error(f"解析Bot {bot_id} 的default_tags失败: {str(e)}")
            current_tags = {}

        # 更新childBots字段，保留其他字段
        current_tags["childBots"] = child_bots

        # 更新bot的tags
        update_data = BotForUpdate(is_default_tags_updated=True, default_tags=json.dumps(current_tags))
        bot_tool.run(action="update", bot_id=bot_id, data=update_data)
        log.info(f"已更新Bot {bot_id} 的childBots列表，保留了现有的tags字段")
    except Exception as e:
        log.error(f"更新Bot {bot_id} 的childBots列表失败: {str(e)}")


async def get_child_bot_opera_ids(bot_tool: BotTool, child_bot_id: str, log) -> Set[str]:
    """获取ChildBot管理的Opera IDs"""
    try:
        parser = ApiResponseParser()
        child_bot_info = bot_tool.run(action="get", bot_id=child_bot_id)
        _, child_data = parser.parse_response(child_bot_info)
        child_tags = parser.parse_default_tags(child_data)

        if child_tags and "related_operas" in child_tags:
            return set(child_tags["related_operas"])

        # 通过API获取
        staffs_result = bot_tool.run(
            action="get_all_staffs",
            bot_id=child_bot_id,
            data={"need_opera_info": True, "need_staffs": 1, "need_staff_invitations": 0},
        )
        _, staffs_data = parser.parse_response(staffs_result)
        child_operas = set(str(opera["operaId"]) for opera in staffs_data if opera.get("staffs"))
        log.warning(f"ChildBot {child_bot_id} 缺少managed_operas标签，已通过API获取到 {len(child_operas)} 个opera")
        return child_operas
    except Exception as e:
        log.error(f"获取ChildBot {child_bot_id} 信息失败: {str(e)}")
        return set()


async def get_child_bot_staff_info(bot_tool: BotTool, child_bot_id: str, log) -> dict:
    """获取ChildBot的staff信息和roles"""
    try:
        parser = ApiResponseParser()
        staffs_result = bot_tool.run(
            action="get_all_staffs",
            bot_id=child_bot_id,
            data={"need_opera_info": True, "need_staffs": 1, "need_staff_invitations": 0},
        )
        _, staffs_data = parser.parse_response(staffs_result)

        staff_info = {}
        for opera in staffs_data:
            opera_id = str(opera["operaId"])
            staff_info[opera_id] = {
                "staff_ids": [UUID(staff["id"]) for staff in opera.get("staffs", [])],
                "roles": [staff.get("roles", "").split(",") for staff in opera.get("staffs", [])],
            }
        log.info(f"获取到ChildBot {child_bot_id} 的staff信息: {len(staff_info)}个opera")
        return staff_info
    except Exception as e:
        log.error(f"获取ChildBot {child_bot_id} 的staff信息失败: {str(e)}")
        return {}
