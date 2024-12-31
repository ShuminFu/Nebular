import unittest
from uuid import UUID
from datetime import datetime, timezone
from Opera.core.crew_process import CrewManager
from Opera.core.task_utils import TaskType, TaskStatus, TaskPriority, BotTask
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from Opera.core.tests.test_task_utils import AsyncTestCase
from ai_core.tools.opera_api.resource_api_tool import _SHARED_RESOURCE_TOOL, Resource
import asyncio


class TestMultiResourceGeneration(AsyncTestCase):
    """测试多文件资源生成功能
    
    主要测试点：
    1. 多文件任务的拆分
    2. 任务间上下文共享
    3. 并行处理能力
    4. 错误处理机制
    
    与test_resource_creation.py的区别：
    - 这个测试文件专注于多文件生成场景
    - 测试任务拆分和上下文共享
    - 验证并行处理性能
    - 关注多文件场景下的错误处理
    """

    def setUp(self):
        """设置测试环境"""
        # 创建测试用的Bot IDs
        self.cm_bot_id = UUID('4a4857d6-4664-452e-a37c-80a628ca28a0')  # CM的Bot ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')  # 测试用Opera ID
        self.user_staff_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')  # 用户的Staff ID
        self.cm_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')  # CM的Staff ID

        # 创建CrewManager实例
        self.crew_manager = CrewManager()
        self.crew_manager.bot_id = self.cm_bot_id

        # 设置通用的测试时间
        self.test_time = datetime.now(timezone.utc).isoformat()

        # 缓存CM的staff_id
        self.crew_manager._staff_id_cache[str(self.test_opera_id)] = self.cm_staff_id

        # 初始化CrewManager
        self.run_async(self._init_crew_manager())

    async def _init_crew_manager(self):
        """初始化CrewManager，但不进入主循环"""
        # 保存原始的is_running值
        original_is_running = self.crew_manager.is_running
        # 设置is_running为False，这样run方法会在setup后立即返回
        self.crew_manager.is_running = False
        try:
            await self.crew_manager.run()
        finally:
            # 恢复原始的is_running值
            self.crew_manager.is_running = original_is_running

    def create_test_message(self, text: str, opera_id: UUID) -> MessageReceivedArgs:
        """创建测试用的消息对象
        
        创建一个原始的消息对象，模拟用户发送的前端项目代码生成请求。
        消息会通过对话池的分析器添加intent_analysis。
        """
        return MessageReceivedArgs(
            index=1,
            text=text,
            tags="",  # 使用基础标签，让分析器来识别具体意图
            sender_staff_id=self.user_staff_id,
            opera_id=opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id, self.user_staff_id],
            time=self.test_time,
            stage_index=1
        )

    def test_multiple_file_generation(self):
        """测试多文件生成功能"""
        self.run_async(self._test_multiple_file_generation())

    def test_parallel_task_processing(self):
        """测试并行处理多个任务"""
        self.run_async(self._test_parallel_task_processing())

    def test_task_error_handling(self):
        """测试任务错误处理"""
        self.run_async(self._test_task_error_handling())

    async def _test_multiple_file_generation(self):
        """测试多文件生成功能的具体实现"""
        # 创建测试消息
        message = self.create_test_message(
            """请创建一个响应式的产品展示页面，包含以下功能：
            1. 主页面(index.html)：
               - 响应式网格布局展示产品
               - 产品过滤功能
            2. 样式文件：
               - 主样式(main.css)：响应式布局
               - 产品卡片样式(product-card.css)
            3. JavaScript文件：
               - 主逻辑(main.js)：实现产品过滤
               - 模态框(product-modal.js)：产品详情展示
            4. 依赖：
               - normalize.css用于样式重置
               - @popperjs/core用于模态框定位""",
            self.test_opera_id
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取创建的任务
        tasks = []
        while True:
            task = self.crew_manager.task_queue.get_next_task()
            if not task:
                break
            tasks.append(task)
            # 更新任务状态为RUNNING，这样get_next_task就不会重复获取同一个任务
            await self.crew_manager.task_queue.update_task_status(task.id, TaskStatus.RUNNING)

        # 验证任务数量至少有3个（至少包含HTML、CSS、JS各一个）
        self.assertGreaterEqual(len(tasks), 3, "至少应该有HTML、CSS、JS各一个文件")

        # 验证每个任务的基本属性
        expected_file_types = {
            "html": {
                "mime": "text/html",
                "found": False  # 是否找到此类型的文件
            },
            "css": {
                "mime": "text/css",
                "found": False
            },
            "javascript": {
                "mime": "text/javascript",
                "found": False
            }
        }

        # 统计实际的文件类型
        for task in tasks:
            file_path = task.parameters["file_path"]
            mime_type = task.parameters["mime_type"]

            if mime_type == "text/html":
                expected_file_types["html"]["found"] = True
            elif mime_type == "text/css":
                expected_file_types["css"]["found"] = True
            elif mime_type == "text/javascript":
                expected_file_types["javascript"]["found"] = True

        # 验证是否每种类型的文件都至少有一个
        for file_type, info in expected_file_types.items():
            self.assertTrue(
                info["found"],
                f"应该至少有一个 {file_type} 文件"
            )

        # 验证每个任务的属性
        first_dialogue_context = None
        for task in tasks:
            # 验证任务类型
            self.assertEqual(task.type, TaskType.RESOURCE_GENERATION)
            # 验证任务优先级
            self.assertEqual(task.priority, TaskPriority.HIGH)
            # 验证MIME类型格式是否正确
            self.assertIn(
                task.parameters["mime_type"],
                [info["mime"] for info in expected_file_types.values()],
                f"文件 {task.parameters['file_path']} 的MIME类型 {task.parameters['mime_type']} 不在预期范围内"
            )
            # 验证Opera ID
            self.assertEqual(task.parameters["opera_id"], str(self.test_opera_id))

            # 验证项目级别的上下文
            code_details = task.parameters.get("code_details", {})
            self.assertEqual(code_details.get("project_type"), "web")
            self.assertIn("@popperjs/core", code_details.get("frameworks", []))
            self.assertIn("normalize.css", code_details.get("frameworks", []))

            # 验证是否包含所有文件的信息
            resources = code_details.get("resources", [])
            self.assertGreaterEqual(len(resources), 3, "每个任务都应该包含至少3个文件的信息")

            # 验证所有任务的对话上下文是否一致
            dialogue_context = task.parameters.get("dialogue_context", {})
            if first_dialogue_context is None:
                first_dialogue_context = dialogue_context
            else:
                # 验证对话ID一致
                self.assertEqual(
                    dialogue_context.get("dialogue_id"),
                    first_dialogue_context.get("dialogue_id"),
                    "所有任务的对话ID应该一致"
                )

                # 验证其他上下文字段一致
                self.assertEqual(
                    set(dialogue_context.keys()),
                    set(first_dialogue_context.keys()),
                    "所有任务的对话上下文字段应该一致"
                )

        # 返回生成的任务列表供其他测试使用
        return tasks

    async def _test_parallel_task_processing(self):
        """测试并行处理多个资源创建任务"""
        # 复用_test_multiple_file_generation生成的任务
        tasks = await self._test_multiple_file_generation()

        # 并行处理所有任务
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(
            *[self.crew_manager.resource_handler.handle_resource_creation(task) for task in tasks]
        )
        end_time = asyncio.get_event_loop().time()

        # 验证总处理时间
        processing_time = end_time - start_time
        # self.assertLess(
        #     processing_time,
        #     2.0,  # 考虑到多个文件的API调用开销，设置为2秒
        #     "并行处理的总时间应该在合理范围内"
        # )

        # 验证所有任务是否都完成了
        for task in tasks:
            self.assertEqual(task.status, TaskStatus.COMPLETED)
            self.assertIsNotNone(task.result.get("resource_id"))

            # 验证资源是否存在
            resource_result = await asyncio.to_thread(
                _SHARED_RESOURCE_TOOL.run,
                action="get",
                opera_id=str(self.test_opera_id),
                resource_id=UUID(task.result["resource_id"])
            )
            self.assertIsInstance(resource_result, Resource)
            self.assertEqual(resource_result.name, task.parameters["file_path"])

    async def _test_task_error_handling(self):
        """测试任务错误处理的具体实现"""
        # 创建测试消息，包含一些故意的错误
        message = self.create_test_message(
            """请创建以下文件：
            1. 空路径文件
            2. 带无效扩展名的样式文件(.xyz)
            3. 正常的HTML、CSS和JS文件""",
            self.test_opera_id
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取所有任务
        tasks = []
        while True:
            task = self.crew_manager.task_queue.get_next_task()
            if not task:
                break
            tasks.append(task)

        # 验证任务数量（应该忽略无效的资源配置）
        self.assertEqual(len(tasks), 5, "应该只创建有效的任务")

        # 验证所有任务的文件路径都是有效的
        for task in tasks:
            self.assertTrue(task.parameters["file_path"])
            # 验证文件扩展名与MIME类型匹配
            file_ext = task.parameters["file_path"].split(".")[-1]
            mime_type = task.parameters["mime_type"]
            self.assertTrue(
                (file_ext == "html" and mime_type == "text/html") or
                (file_ext == "css" and mime_type == "text/css") or
                (file_ext == "js" and mime_type == "text/javascript"),
                f"文件扩展名 {file_ext} 应该与MIME类型 {mime_type} 匹配"
            )

    def tearDown(self):
        """清理测试环境"""
        self.run_async(self._tearDown())

    async def _tearDown(self):
        # 清理缓存
        self.crew_manager._staff_id_cache.clear()
        # 清理任务队列
        self.crew_manager.task_queue.tasks.clear()
        # 清理对话池
        if hasattr(self.crew_manager, 'intent_processor'):
            self.crew_manager.intent_processor.dialogue_pool.dialogues.clear()

        # 清理测试过程中创建的资源
        try:
            # 获取所有资源
            resources = await asyncio.to_thread(
                _SHARED_RESOURCE_TOOL.run,
                action="get_filtered",
                opera_id=str(self.test_opera_id),
                data={
                    "name_like": "src/"  # 匹配测试中创建的资源
                }
            )

            # 删除资源
            if resources:
                for resource in resources:
                    await asyncio.to_thread(
                        _SHARED_RESOURCE_TOOL.run,
                        action="delete",
                        opera_id=str(self.test_opera_id),
                        resource_id=resource.id
                    )
        except Exception as e:
            print(f"清理资源时出错: {e}")


if __name__ == '__main__':
    unittest.main()
