import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import UUID
import re

from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.core.crew_process import CrewRunner
from src.core.task_utils import TaskType, TaskPriority, TaskStatus, BotTask


# 创建枚举模拟器来解析字符串中的枚举值
def parse_enum_from_str(enum_class, enum_str):
    """从字符串中解析枚举值"""
    # 例如从"<TaskPriority.HIGH: 3>"解析出TaskPriority.HIGH
    match = re.search(r"([A-Za-z]+)\.([A-Z_]+)", enum_str)
    if match:
        enum_name = match.group(2)
        return getattr(enum_class, enum_name)
    return None


class TestCrewRunner(unittest.IsolatedAsyncioTestCase):
    """CrewRunner测试类"""

    async def asyncSetUp(self):
        """设置异步测试环境"""
        # 创建一个CrewRunner实例
        with patch("src.core.crew_process.OperaSignalRClient"):
            with patch("src.core.crew_process.get_logger_with_trace_id"):
                with patch("src.core.crew_process.RunnerChatCrew"):
                    with patch("src.core.crew_process.RunnerCodeGenerationCrew"):
                        self.crew_runner = CrewRunner(bot_id=UUID("12345678-1234-5678-1234-567812345678"))

        # 模拟任务队列
        self.crew_runner.task_queue = AsyncMock()
        self.crew_runner.task_queue.add_task = AsyncMock()

        # 模拟日志
        self.crew_runner.log = MagicMock()

    async def test_handle_task_assignment_message(self):
        """测试处理任务分配消息"""
        # 示例任务数据
        task_id = "96ee7a8c-b6dd-4b86-ab21-6dd3fb5a18c0"
        task_str = """{'Id': '96ee7a8c-b6dd-4b86-ab21-6dd3fb5a18c0', 'CreatedAt': '2025-02-25T17:04:48.104183+08:00', 'StartedAt': None, 'CompletedAt': None, 'Priority': <TaskPriority.HIGH: 3>, 'Type': <TaskType.RESOURCE_GENERATION: 51>, 'Status': <TaskStatus.RUNNING: 2>, 'Description': '生成代码文件: /src/css/style.css', 'Parameters': {'file_path': '/src/css/style.css', 'file_type': 'css', 'mime_type': 'text/css', 'description': '页面样式文件', 'references': [], 'code_details': {'project_type': 'web', 'project_description': '智慧物流官网开发，展示企业信息，服务内容和联系方式。', 'requirements': ['设计友好的用户界面', '展示企业信息', '包含公司基本联系方式'], 'frameworks': ['normalize.css'], 'resources': [{'file_path': '/src/html/index.html', 'type': 'html', 'mime_type': 'text/html', 'description': '官网的主页面文件', 'references': ['style.css', 'main.js']}, {'file_path': '/src/css/style.css', 'type': 'css', 'mime_type': 'text/css', 'description': '页面样式文件'}, {'file_path': '/src/js/main.js', 'type': 'javascript', 'mime_type': 'text/javascript', 'description': '前端交互脚本'}]}, 'dialogue_context': {'text': '写一个智慧物流的官网网站', 'type': 'CODE_RESOURCE', 'tags': 'code_request,code_type_css,code_type_html,code_type_javascript,framework_normalize.css', 'intent': '创建智慧物流官网的代码生成请求', 'stage_index': None, 'related_dialogue_indices': [48], 'conversation_state': {'topic': {'id': '431df540-688d-4e5a-be42-e663b2ce8b5e', 'type': 'CODE_RESOURCE', 'name': '智慧物流官网代码生成'}, 'analyzed_at': '2025-02-25T17:04:44.278437+08:00'}, 'flow': {'current_topic': '智慧物流官网代码生成', 'topic_id': '431df540-688d-4e5a-be42-e663b2ce8b5e', 'topic_type': 'CODE_RESOURCE', 'status': 'active', 'derived_from': None, 'change_reason': None, 'evolution_chain': ['431df540-688d-4e5a-be42-e663b2ce8b5e'], 'previous_topics': []}, 'code_context': {'requirements': ['创建智慧物流官网的代码'], 'frameworks': ['normalize.css'], 'file_structure': [], 'api_choices': []}, 'decision_points': [{'decision': '提出了创建智慧物流官网代码的需求', 'reason': '用户明确表达生成代码需求', 'dialogue_index': '48', 'topic_id': '431df540-688d-4e5a-be42-e663b2ce8b5e'}], 'related_dialogues': []}, 'opera_id': '99a51bfa-0b95-46e5-96b3-e3cfc021a6b2', 'parent_topic_id': '0'}, 'SourceDialogueIndex': 48, 'ResponseStaffId': 'c1541b83-4ce5-4a68-b492-596982adf71d', 'SourceStaffId': '5dbe6ee3-bc88-4718-a352-5bb151b5f428', 'TopicId': '431df540-688d-4e5a-be42-e663b2ce8b5e', 'TopicType': 'CODE_RESOURCE', 'Progress': 0, 'Result': None, 'ErrorMessage': None, 'RetryCount': 0, 'LastRetryAt': None}"""
        tags = "TASK_ASSIGNMENT;TASK_ID:96ee7a8c-b6dd-4b86-ab21-6dd3fb5a18c0"

        # 创建消息
        message = MessageReceivedArgs(
            index=1,
            text=task_str,
            sender_staff_id=UUID("00000000-0000-0000-0000-000000000001"),
            is_whisper=True,
            tags=tags,
            opera_id="99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            mentioned_staff_ids=[UUID("c1541b83-4ce5-4a68-b492-596982adf71d")],
            receiver_staff_ids=None,
        )

        # 使用补丁避免对eval()的调用
        with patch("builtins.eval", side_effect=Exception("eval is unsafe")):
            # 模拟从字符串到字典的转换过程
            with patch.object(
                CrewRunner,
                "_parse_task_str",
                return_value={
                    "Id": task_id,
                    "Priority": TaskPriority.HIGH,
                    "Type": TaskType.RESOURCE_GENERATION,
                    "Status": TaskStatus.RUNNING,
                    "Description": "生成代码文件: /src/css/style.css",
                    "Parameters": {"file_path": "/src/css/style.css", "opera_id": "99a51bfa-0b95-46e5-96b3-e3cfc021a6b2"},
                    "SourceDialogueIndex": 48,
                    "ResponseStaffId": "c1541b83-4ce5-4a68-b492-596982adf71d",
                    "SourceStaffId": "5dbe6ee3-bc88-4718-a352-5bb151b5f428",
                    "TopicId": "431df540-688d-4e5a-be42-e663b2ce8b5e",
                    "TopicType": "CODE_RESOURCE",
                },
            ):
                # 调用被测试的方法
                await self.crew_runner._handle_task_assignment_message(message)

        # 验证任务是否被正确添加到队列
        self.crew_runner.task_queue.add_task.assert_called_once()

        # 检查调用add_task的参数
        task_arg = self.crew_runner.task_queue.add_task.call_args[0][0]
        self.assertIsInstance(task_arg, BotTask)
        self.assertEqual(str(task_arg.id), task_id)
        self.assertEqual(task_arg.priority, TaskPriority.HIGH)
        self.assertEqual(task_arg.type, TaskType.RESOURCE_GENERATION)
        self.assertEqual(task_arg.status, TaskStatus.PENDING)  # 注意状态应该是PENDING而不是RUNNING
        self.assertEqual(task_arg.topic_id, "431df540-688d-4e5a-be42-e663b2ce8b5e")

        # 验证日志记录
        self.crew_runner.log.info.assert_called_with(f"已成功将任务 {task_id} 直接添加到任务队列")

    async def test_handle_task_assignment_message_no_task_id(self):
        """测试当消息中没有任务ID时的处理"""
        # 创建没有任务ID的消息
        message = MessageReceivedArgs(
            index=1,
            text="{'Description': 'Test task without ID'}",
            sender_staff_id=UUID("00000000-0000-0000-0000-000000000001"),
            is_whisper=True,
            tags="TASK_ASSIGNMENT",  # 没有TASK_ID标签
            opera_id="99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            mentioned_staff_ids=None,
            receiver_staff_ids=None,
        )

        # 模拟_parse_task_str返回没有Id字段的字典
        with patch.object(CrewRunner, "_parse_task_str", return_value={"Description": "Test task without ID"}):
            # 模拟super()._handle_message
            with patch("src.core.crew_process.BaseCrewProcess._handle_message", new_callable=AsyncMock):
                await self.crew_runner._handle_task_assignment_message(message)

        # 验证日志记录了错误
        self.crew_runner.log.error.assert_called_with("无法从消息中获取任务ID")
        # 验证没有调用add_task
        self.crew_runner.task_queue.add_task.assert_not_called()

    async def test_handle_task_assignment_message_parsing_error(self):
        """测试解析消息失败时的处理"""
        # 创建无法解析的消息
        message = MessageReceivedArgs(
            index=1,
            text="This is not a valid task data",
            sender_staff_id=UUID("00000000-0000-0000-0000-000000000001"),
            is_whisper=True,
            tags="TASK_ASSIGNMENT;TASK_ID:12345",
            opera_id="99a51bfa-0b95-46e5-96b3-e3cfc021a6b2",
            mentioned_staff_ids=None,
            receiver_staff_ids=None,
        )

        # 模拟_parse_task_str抛出异常
        error_msg = "无法解析任务数据"
        with patch.object(CrewRunner, "_parse_task_str", side_effect=Exception(error_msg)):
            # 模拟super()._handle_message
            with patch("src.core.crew_process.BaseCrewProcess._handle_message", new_callable=AsyncMock):
                await self.crew_runner._handle_task_assignment_message(message)

        # 验证日志记录了错误
        self.crew_runner.log.error.assert_called_with(f"解析任务数据失败: {error_msg}")
        # 验证调用了父类的_handle_message方法
        self.crew_runner._handle_message.assert_called_once_with(message)


if __name__ == "__main__":
    unittest.main()
