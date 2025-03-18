"""最小可行性示例，测试对话->对话池->任务队列的基本流程。"""
import asyncio
from uuid import UUID
from datetime import datetime, timezone, timedelta
import unittest

from src.core.intent_mind import IntentMind, parse_version_id
from src.core.task_utils import BotTaskQueue, TaskType
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.core.dialogue.models import ProcessingDialogue, DialogueContext
from src.core.dialogue.enums import DialogueType, ProcessingStatus


# 添加异步测试支持
def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))

    return wrapper


class TestIntentMind(unittest.TestCase):
    """测试IntentMind的核心功能"""

    def setUp(self):
        """测试前的准备工作"""
        self.bot_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')
        self.task_queue = BotTaskQueue(bot_id=self.bot_id)
        self.intent_mind = IntentMind(self.task_queue)
        self.opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        self.test_time = datetime.now(timezone(timedelta(hours=8)))

    def test_parse_tags_with_json(self):
        """测试解析带有JSON结构的标签并提取VersionId"""

        # 测试带JSON的tags字符串
        complex_tags = """{\r\n "ResourcesForViewing": {\r\n "VersionId": "6a737f18-4d82-496f-8f63-5367e897c583",\r\n "Resources": [\r\n {\r\n "Url": "/src/js/main.js",\r\n "ResourceId": "1679d89d-40d3-4db2-b7f5-a48881d3aa31",\r\n "ResourceCacheable": true\r\n },\r\n {\r\n "Url": "/src/css/style.css",\r\n "ResourceId": "368e4fd9-e40b-4b18-a48b-1003e71c4aac",\r\n "ResourceCacheable": true\r\n },\r\n {\r\n "Url": "/src/html/index.html",\r\n "ResourceId": "18c91231-af74-4704-9960-eff96164428b",\r\n "ResourceCacheable": true\r\n }\r\n ],\r\n "NavigateIndex": 0\r\n }\r\n},code_request,code_type_html,code_type_js,code_type_css,framework_jquery,framework_bootstrap"""

        # 解析tags
        parsed_tags = self.intent_mind._parse_tags(complex_tags)

        # 测试是否成功解析出JSON部分和普通标签
        self.assertTrue(len(parsed_tags) > 1, "应该解析出多个标签")
        self.assertTrue(parsed_tags[0].startswith("{"), "第一个标签应该是JSON结构")
        self.assertIn("code_request", parsed_tags, "应该包含普通标签")

        # 测试version_id提取
        version_id = parse_version_id(parsed_tags)
        expected_version_id = "6a737f18-4d82-496f-8f63-5367e897c583"
        self.assertEqual(version_id, expected_version_id, f"VersionId不匹配: 期望 {expected_version_id}, 得到 {version_id}")

    @async_test
    async def test_create_task_from_dialogue_with_context(self):
        """测试从带有上下文的对话创建任务"""
        # 创建一个测试对话，包含完整的上下文信息
        dialogue = ProcessingDialogue(
            dialogue_index=231,
            opera_id=self.opera_id,
            text="```html\n<div>Test Code</div>\n```",
            type=DialogueType.CODE_RESOURCE,
            status=ProcessingStatus.PENDING,
            context=DialogueContext(
                stage_index=2,
                related_dialogue_indices=[229, 230],
                conversation_state={
                    "flow": {
                        "current_topic": "Web Development",
                        "topic_id": "550e8400-e29b-41d4-a716-446655440000",
                        "topic_type": "code_generation",
                        "previous_topics": [],
                        "status": "ongoing"
                    },
                    "code_context": {
                        "requirements": ["Responsive Design"],
                        "frameworks": ["normalize.css"],
                        "file_structure": ["src/html/index.html"]
                    },
                    "decision_points": [
                        {
                            "decision": "Use normalize.css",
                            "reason": "For consistent styling",
                            "dialogue_index": 229,
                            "topic_id": "550e8400-e29b-41d4-a716-446655440000"
                        }
                    ],
                    "topic": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "type": "code_generation",
                        "name": "Web Development",
                        "last_updated": self.test_time.isoformat()
                    }
                }
            ),
            timestamp=self.test_time,
            sender_staff_id=UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc'),
            is_narratage=False,
            is_whisper=False,
            tags="CODE_RESOURCE",
            mentioned_staff_ids=[]
        )

        # 添加相关对话到对话池
        related_dialogue1 = ProcessingDialogue(
            dialogue_index=229,
            opera_id=self.opera_id,
            text="Let's use normalize.css for consistent styling",
            type=DialogueType.NORMAL,
            status=ProcessingStatus.COMPLETED,
            context=DialogueContext(
                stage_index=2,
                related_dialogue_indices=[],
                conversation_state={}
            ),
            timestamp=self.test_time - timedelta(minutes=2)
        )

        related_dialogue2 = ProcessingDialogue(
            dialogue_index=230,
            opera_id=self.opera_id,
            text="We need responsive design",
            type=DialogueType.NORMAL,
            status=ProcessingStatus.COMPLETED,
            context=DialogueContext(
                stage_index=2,
                related_dialogue_indices=[],
                conversation_state={}
            ),
            timestamp=self.test_time - timedelta(minutes=1)
        )

        self.intent_mind.dialogue_pool.dialogues = [related_dialogue1, related_dialogue2, dialogue]

        # 创建任务，添加await
        task_result = await self.intent_mind._create_task_from_dialogue(dialogue)

        # 检查返回值类型，可能是单个任务或任务列表
        if isinstance(task_result, list):
            self.assertEqual(len(task_result), 1)
            task = task_result[0]
        else:
            task = task_result

        # 验证任务类型
        # 注意：根据实现的不同，这可能是RESOURCE_CREATION或RESOURCE_GENERATION
        self.assertIn(task.type, [TaskType.RESOURCE_CREATION, TaskType.RESOURCE_GENERATION])

        # 验证任务参数中的上下文信息
        self.assertIn("context", task.parameters)
        context = task.parameters["context"]

        # 验证基本上下文字段
        self.assertEqual(context["stage_index"], 2)
        self.assertEqual(set(context["related_dialogue_indices"]), {229, 230})

        # 验证对话流程信息
        flow = context["flow"]
        self.assertEqual(flow["topic_id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(flow["topic_type"], "code_generation")
        self.assertEqual(flow["current_topic"], "Web Development")

        # 验证代码上下文
        code_context = context["code_context"]
        self.assertIn("Responsive Design", code_context["requirements"])
        self.assertIn("normalize.css", code_context["frameworks"])
        self.assertIn("src/html/index.html", code_context["file_structure"])

        # 验证决策点
        decision_points = context["decision_points"]
        self.assertEqual(len(decision_points), 1)
        self.assertEqual(decision_points[0]["dialogue_index"], 229)
        self.assertEqual(decision_points[0]["topic_id"], "550e8400-e29b-41d4-a716-446655440000")

        # 验证主题信息
        topic = context["conversation_state"]["topic"]
        self.assertEqual(topic["id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(topic["type"], "code_generation")
        self.assertEqual(topic["name"], "Web Development")

    @async_test
    async def test_create_direct_generation_task(self):
        """测试创建直接生成任务（没有action字段）"""
        # 创建一个测试对话，模拟直接生成代码请求
        dialogue = ProcessingDialogue(
            dialogue_index=232,
            opera_id=self.opera_id,
            text="请创建一个简单的Python计算器",
            type=DialogueType.CODE_RESOURCE,
            status=ProcessingStatus.PENDING,
            context=DialogueContext(
                stage_index=1,
                related_dialogue_indices=[],
                conversation_state={
                    "topic": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "type": "code_generation",
                        "name": "Python Calculator",
                    }
                },
            ),
            timestamp=self.test_time,
            sender_staff_id=UUID("ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc"),
            is_narratage=False,
            is_whisper=False,
            tags="CODE_RESOURCE",
            mentioned_staff_ids=[],
            intent_analysis=None,  # 稍后设置
        )

        # 设置intent_analysis，不包含action字段
        from pydantic import BaseModel

        class MockCodeDetails(BaseModel):
            project_type: str = "Python Application"
            project_description: str = "简单的计算器应用"
            resources: list = [
                {
                    "file_path": "src/python/calculator.py",
                    "type": "python",
                    "mime_type": "text/x-python",
                    "description": "实现基本的四则运算",
                }
            ]
            requirements: list = ["支持加减乘除", "处理输入错误"]
            frameworks: list = ["标准库"]

        class MockIntentAnalysis(BaseModel):
            intent: str = "code_generation"
            confidence: float = 0.95
            parameters: dict = {"is_code_request": True, "code_details": MockCodeDetails().model_dump()}

        dialogue.intent_analysis = MockIntentAnalysis()

        # 创建任务，添加await
        tasks = await self.intent_mind._create_task_from_dialogue(dialogue)

        # 验证返回的是任务列表
        self.assertIsInstance(tasks, list)
        self.assertEqual(len(tasks), 1)

        task = tasks[0]

        # 验证任务类型是RESOURCE_GENERATION（直接生成）
        self.assertEqual(task.type, TaskType.RESOURCE_GENERATION)

        # 验证任务描述包含"生成"而不是"迭代"
        self.assertIn("生成代码文件", task.description)
        self.assertNotIn("迭代代码文件", task.description)

        # 验证任务参数中没有action相关字段
        self.assertNotIn("action", task.parameters)
        self.assertNotIn("position", task.parameters)
        self.assertNotIn("resource_id", task.parameters)

        # 验证parent_topic_id为"0"
        self.assertEqual(task.parameters["parent_topic_id"], "0")

    @async_test
    async def test_create_iteration_task(self):
        """测试创建迭代任务（包含action字段）"""
        # 创建一个测试对话，模拟代码迭代请求
        dialogue = ProcessingDialogue(
            dialogue_index=233,
            opera_id=self.opera_id,
            text="请在计算器中添加开方功能，并修复乘法bug",
            type=DialogueType.CODE_RESOURCE,
            status=ProcessingStatus.PENDING,
            context=DialogueContext(
                stage_index=2,
                related_dialogue_indices=[],
                conversation_state={
                    "topic": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "type": "code_generation",
                        "name": "Python Calculator",
                    }
                },
            ),
            timestamp=self.test_time,
            sender_staff_id=UUID("ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc"),
            is_narratage=False,
            is_whisper=False,
            tags="CODE_RESOURCE;{'ResourcesForViewing':{'VersionId':'v1.0'}}",
            mentioned_staff_ids=[],
            intent_analysis=None,  # 稍后设置
        )

        # 设置intent_analysis，包含action字段
        from pydantic import BaseModel

        class MockCodeDetails(BaseModel):
            project_type: str = "Python Application"
            project_description: str = "简单的计算器应用迭代"
            resources: list = [
                {
                    "file_path": "src/python/calculator.py",
                    "type": "python",
                    "mime_type": "text/x-python",
                    "description": "修复乘法bug",
                    "action": "update",
                    "position": "multiply函数",
                    "resource_id": "res-001",
                },
                {
                    "file_path": "src/python/math_functions.py",
                    "type": "python",
                    "mime_type": "text/x-python",
                    "description": "添加开方功能",
                    "action": "create",
                    "position": "全部",
                    "resource_id": "res-002",
                },
            ]
            requirements: list = ["添加开方功能", "修复乘法bug"]
            frameworks: list = ["标准库"]

        class MockIntentAnalysis(BaseModel):
            intent: str = "code_iteration"
            confidence: float = 0.95
            parameters: dict = {"is_code_request": True, "code_details": MockCodeDetails().model_dump()}

        dialogue.intent_analysis = MockIntentAnalysis()

        # 创建任务，添加await
        tasks = await self.intent_mind._create_task_from_dialogue(dialogue)

        # 验证返回的是任务列表
        self.assertIsInstance(tasks, list)
        self.assertEqual(len(tasks), 2)

        # 验证所有任务类型都是RESOURCE_ITERATION（迭代）
        for task in tasks:
            self.assertEqual(task.type, TaskType.RESOURCE_ITERATION)

            # 验证任务描述包含"迭代"而不是"生成"
            self.assertIn("迭代代码文件", task.description)
            self.assertNotIn("生成代码文件", task.description)

            # 验证任务参数中包含action相关字段
            self.assertIn("action", task.parameters)
            self.assertIn("position", task.parameters)
            self.assertIn("resource_id", task.parameters)

            # 验证parent_topic_id不为None
            self.assertIsNotNone(task.parameters["parent_topic_id"])


async def main():
    # 1. 创建任务队列和意图识别实例
    bot_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')
    task_queue = BotTaskQueue(bot_id=bot_id)
    intent_mind = IntentMind(task_queue)

    opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
    receiver_staff_ids = [UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')]
    sender_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')

    # 2. 创建一个模拟的消息
    message = MessageReceivedArgs(
        opera_id=opera_id,
        receiver_staff_ids=receiver_staff_ids,
        index=25,
        text="写一个python代码，计算1到100的和",
        sender_staff_id=sender_staff_id,
        time=datetime.now(timezone(timedelta(hours=8))),
        is_narratage=False,
        is_whisper=False,
        tags="query, urgent",
        mentioned_staff_ids=[],
        stage_index=1
    )
    
    # 3. 处理消息
    print("处理消息...")
    await intent_mind.process_message(message)
    
    # 4. 检查对话池状态
    dialogue_pool = intent_mind.get_dialogue_pool()
    print("\n对话池状态:")
    print(f"- 对话数量: {len(dialogue_pool.dialogues)}")
    print(f"- 状态计数: {dialogue_pool.status_counter}")
    
    # 5. 检查第一个对话的详细信息
    if dialogue_pool.dialogues:
        dialogue = dialogue_pool.dialogues[0]
        print("\n对话详情:")
        print(f"- 索引: {dialogue.dialogue_index}")
        print(f"- 优先级: {dialogue.priority}")
        print(f"- 类型: {dialogue.type}")
        print(f"- 状态: {dialogue.status}")
        if dialogue.intent_analysis:
            print(f"- 意图: {dialogue.intent_analysis.intent}")
            print(f"- 置信度: {dialogue.intent_analysis.confidence}")

    # 6. 检查任务队列状态
    print("\n任务队列状态:")
    print(f"- 任务数量: {len(task_queue.tasks)}")
    print(f"- 状态计数: {task_queue.status_counter}")
    
    # 7. 检查第一个任务的详细信息
    if task_queue.tasks:
        task = task_queue.tasks[0]
        print("\n任务详情:")
        print(f"- ID: {task.id}")
        print(f"- 优先级: {task.priority}")
        print(f"- 类型: {task.type}")
        print(f"- 状态: {task.status}")
        print(f"- 描述: {task.description}")
        print(f"- 源对话索引: {task.source_dialogue_index}")
        print(f"- 源Staff ID: {task.response_staff_id}")


if __name__ == "__main__":
    asyncio.run(main())
