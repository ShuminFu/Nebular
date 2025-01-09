"""最小可行性示例，测试对话->对话池->任务队列的基本流程。"""
import asyncio
from uuid import UUID
from datetime import datetime, timezone, timedelta
import unittest

from src.core.intent_mind import IntentMind
from src.core.task_utils import BotTaskQueue, TaskType, TaskPriority
from src.opera_service.signalr_client.opera_signalr_client import MessageReceivedArgs
from src.core.dialogue.models import ProcessingDialogue, DialogueContext
from src.core.dialogue.enums import DialogueType, ProcessingStatus


class TestIntentMind(unittest.TestCase):
    """测试IntentMind的核心功能"""

    def setUp(self):
        """测试前的准备工作"""
        self.bot_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')
        self.task_queue = BotTaskQueue(bot_id=self.bot_id)
        self.intent_mind = IntentMind(self.task_queue)
        self.opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
        self.test_time = datetime.now(timezone(timedelta(hours=8)))

    def test_create_task_from_dialogue_with_context(self):
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

        # 创建任务
        task = self.intent_mind._create_task_from_dialogue(dialogue)

        # 验证任务类型和优先级
        self.assertEqual(task.type, TaskType.RESOURCE_CREATION)

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
        topic = context["topic"]
        self.assertEqual(topic["id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(topic["type"], "code_generation")
        self.assertEqual(topic["name"], "Web Development")


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
