from ai_core.tools.opera_api.bot_api_tool import BotTool,BotToolSchema


def test_bot_tool():
    # 初始化工具
    bot_tool = BotTool()

    tool_input = BotToolSchema(
        action="update",
        bot_id="e822fd9b-a360-4eb7-b217-c4f86f2dcee6",
        data={
            "name": "None",
            "isDescriptionUpdated": True,
            "description": "这是更新后的测试Bot",
            "isCallShellOnOperaStartedUpdated": False,
            "isDefaultTagsUpdated": True,
            "defaultTags": "updated,test",
            "isDefaultRolesUpdated": False,
            "isDefaultPermissionsUpdated": False
        }
    )

    # 直接运行工具
    result = bot_tool._run(**tool_input.model_dump())

    print(f"创建Bot结果: {result}")


if __name__ == "__main__":
    test_bot_tool()