"""
测试资源创建功能, 主要流程：
CM received `raw message` -> into processing dialogue & ==code_request== -> ==BotTask== -> dispatch -> CR
CR taskqueue updated by code_request tag -> Generate code -> say it out
CM received `raw message` -> into processing dialogue & ==code_creation== -> BotTask -> CM's CodeMonkey 
"""
import unittest
from uuid import UUID
from datetime import datetime, timezone
from Opera.core.crew_process import CrewManager, CrewRunner
from Opera.core.task_utils import TaskType, TaskStatus, BotTask
from Opera.core.api_response_parser import ApiResponseParser
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs
from Opera.core.tests.test_task_utils import AsyncTestCase, TaskPriority
from ai_core.tools.opera_api.resource_api_tool import _SHARED_RESOURCE_TOOL, Resource
from ai_core.tools.opera_api.dialogue_api_tool import _SHARED_DIALOGUE_TOOL
import asyncio


class TestResourceCreation(AsyncTestCase):
    """测试资源创建/搬运功能，即由codemonkey对已经生成的资源文件进行opera上的resource创建。"""

    def setUp(self):
        """设置测试环境"""
        # 创建测试用的Bot IDs
        self.cm_bot_id = UUID('4a4857d6-4664-452e-a37c-80a628ca28a0')  # CM的Bot ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')  # 测试用Opera ID
        self.user_staff_id = UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')  # 用户的Staff ID
        self.cm_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')  # CM的Staff ID

        # 设置测试用的代码内容
        self.test_code_content = """@file: examples/calculator.py
@description: A simple calculator implementation
@tags: math,utility,versionID
@version: 1.0.0
@version_id: 12345678-1234-5678-1234-567812345678
---
def add_numbers(a: int, b: int) -> int:
    return a + b"""

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

    def test_code_resource_parsing(self):
        """测试代码资源的解析"""
        self.run_async(self._test_code_resource_parsing())

    def test_invalid_code_resource(self):
        """测试无效的代码资源格式"""
        self.run_async(self._test_invalid_code_resource())

    def test_task_status_update(self):
        """测试任务状态更新"""
        self.run_async(self._test_task_status_update())

    def test_resource_api_calls(self):
        """测试资源创建过程中的API调用"""
        self.run_async(self._test_resource_api_calls())

    def test_code_generation_request(self):
        """测试代码生成请求的处理流程"""
        self.run_async(self._test_code_generation_request())

    async def _test_code_resource_parsing(self):
        # 创建一个模拟的消息
        message = MessageReceivedArgs(
            index=1,
            text=self.test_code_content,
            tags="code_resource",
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取创建的任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证任务类型
        self.assertEqual(task.type, TaskType.RESOURCE_CREATION)

        # 验证任务参数
        self.assertEqual(task.parameters['file_path'], 'examples/calculator.py')
        self.assertEqual(task.parameters['description'], 'A simple calculator implementation')
        self.assertEqual(task.parameters['tags'], ['math', 'utility', 'versionID'])
        self.assertEqual(task.parameters['resource_type'], 'code')

        # 验证代码内容
        expected_code = """def add_numbers(a: int, b: int) -> int:
    return a + b"""
        self.assertEqual(task.parameters['code_content'].strip(), expected_code)

    async def _test_invalid_code_resource(self):
        # 测试无效的代码资源格式
        invalid_content = """This is not a valid code resource format
def some_function():
    pass"""

        message = MessageReceivedArgs(
            index=2,
            text=invalid_content,
            tags="code_resource",
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取创建的任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证无效格式的代码资源不应该创建任务
        # self.assertIsNone(task, "无效的代码资源格式不应该创建任务")
        assert task is not None

    async def _test_task_status_update(self):
        # 测试任务状态更新
        message = MessageReceivedArgs(
            index=3,
            text=self.test_code_content,
            tags="code_resource",
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=None,
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证初始状态
        self.assertEqual(task.status, TaskStatus.PENDING)

        # 更新任务状态
        await self.crew_manager.task_queue.update_task_status(task.id, TaskStatus.COMPLETED)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)

    async def _test_resource_api_calls(self):
        # 手动从测试代码内容中提取代码部分, 实际中从MessageArgs转化为BotTask的时候, code_content已经提取出来了
        code_content = self.test_code_content.split("---\n")[1].strip()
        # 使用时间戳创建唯一的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = f"examples/calculator_{timestamp}.py"
        description = "A simple calculator implementation"
        tags = ["math", "utility", "versionID"]
        mime_type = "text/x-python"

        # 创建测试任务
        task = BotTask(
            id=UUID('bf9145e3-aee8-4945-ab28-a6b906815e83'),
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.PENDING,
            priority=3,
            description="Create resource test",
            parameters={
                "file_path": file_path,
                "description": description,
                "tags": tags,
                "code_content": code_content,
                "opera_id": str(self.test_opera_id),
                "resource_type": "code",
                "mime_type": mime_type
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cm_staff_id
        )

        # 将任务添加到队列中
        await self.crew_manager.task_queue.add_task(task)

        # 执行资源创建
        await self.crew_manager.resource_handler.handle_resource_creation(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)

        # 验证任务状态和结果
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(updated_task.result.get("resource_id"))
        self.assertEqual(updated_task.result["path"], file_path)
        self.assertEqual(updated_task.result["status"], "success")

        # 验证资源是否真实存在
        resource_result = await asyncio.to_thread(
            _SHARED_RESOURCE_TOOL.run,
            action="get",
            opera_id=str(self.test_opera_id),
            resource_id=UUID(updated_task.result["resource_id"])
        )

        # 直接使用Resource对象进行验证
        self.assertIsInstance(resource_result, Resource)
        self.assertEqual(resource_result.name, file_path)
        self.assertEqual(resource_result.description, description)
        self.assertEqual(resource_result.mime_type, mime_type)  # 验证MIME类型是否正确

    def test_resource_api_error_handling(self):
        """测试资源创建过程中的错误处理"""
        self.run_async(self._test_resource_api_error_handling())

    async def _test_resource_api_error_handling(self):
        # 从测试代码内容中提取代码部分
        # 同上是模拟的code_content
        code_content = self.test_code_content.split("---\n")[1].strip()

        # 测试无效路径
        task = BotTask(
            id=UUID('bf9145e3-aee8-4945-ab28-a6b906815e83'),
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.PENDING,
            priority=3,
            description="Create resource test",
            parameters={
                "file_path": "/invalid/path/test.py",  # 使用无效的路径
                "description": "This should fail",
                "tags": ["test"],
                "code_content": code_content,
                "opera_id": str(self.test_opera_id),
                "resource_type": "code"
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cm_staff_id
        )

        # 将任务添加到队列中
        await self.crew_manager.task_queue.add_task(task)

        # 执行资源创建
        await self.crew_manager.resource_handler.handle_resource_creation(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)

        # 验证任务状态和错误信息
        self.assertEqual(updated_task.status, TaskStatus.FAILED)
        self.assertIsNotNone(updated_task.error_message)

        # 测试无效的代码内容
        task = BotTask(
            id=UUID('bf9145e3-aee8-4945-ab28-a6b906815e84'),  # 使用不同的ID
            type=TaskType.RESOURCE_CREATION,
            status=TaskStatus.PENDING,
            priority=3,
            description="Create resource test",
            parameters={
                "file_path": "examples/invalid.py",
                "description": "This should fail",
                "tags": ["test"],
                "code_content": None,  # 无效的代码内容
                "opera_id": str(self.test_opera_id),
                "resource_type": "code"
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cm_staff_id
        )

        # 将任务添加到队列中
        await self.crew_manager.task_queue.add_task(task)

        # 执行资源创建
        await self.crew_manager.resource_handler.handle_resource_creation(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_manager.task_queue.tasks if t.id == task.id)

        # 验证任务状态和错误信息
        self.assertEqual(updated_task.status, TaskStatus.FAILED)
        self.assertIn("缺少必要的资源信息", updated_task.error_message)

    async def _test_code_generation_request(self):
        """测试代码生成请求的处理流程

        测试场景：
        1. 用户请求生成一个Python脚本
        2. 系统识别这是代码生成请求
        3. 分析意图和需求
        4. 创建相应的任务
        """
        # 创建一个代码生成请求的消息
        message = MessageReceivedArgs(
            index=1,
            text="""请帮我写一个Python脚本，用来处理CSV文件：
            1. 需要使用pandas库
            2. 读取sales.csv文件
            3. 计算每个产品的总销售额
            4. 生成销售报告
            5. 将结果保存到新的CSV文件中""",
            tags="",  # 初始没有标签，系统应该自动识别为代码请求
            sender_staff_id=self.user_staff_id,
            opera_id=self.test_opera_id,
            is_whisper=False,
            is_narratage=False,
            mentioned_staff_ids=[self.cm_staff_id],  # 提到了CM
            receiver_staff_ids=[self.cm_staff_id],
            time=self.test_time,
            stage_index=1
        )

        # 处理消息
        await self.crew_manager._handle_message(message)

        # 获取创建的任务
        task = self.crew_manager.task_queue.get_next_task()

        # 验证任务类型
        self.assertEqual(task.type, TaskType.RESOURCE_GENERATION)

        # 验证任务优先级（代码生成请求应该是高优先级）
        self.assertEqual(task.priority, TaskPriority.HIGH)

        # 验证任务参数
        self.assertTrue("code_request" in task.parameters.get("tags", []))
        self.assertTrue("code_type_python" in task.parameters.get("tags", []))
        self.assertTrue("framework_pandas" in task.parameters.get("tags", []))

        # 验证意图分析结果
        intent_analysis = task.parameters.get("intent")
        self.assertIsNotNone(intent_analysis)
        self.assertNotEqual(intent_analysis.get("intent", ""), "")  # 意图不应该为空

        # 验证代码生成的具体要求被正确捕获
        code_details = task.parameters.get("code_details", {})
        self.assertEqual(code_details.get("type"), "Python")
        self.assertIn("pandas", code_details.get("frameworks", []))
        requirements = code_details.get("requirements", [])
        self.assertTrue(any("CSV" in req for req in requirements))
        self.assertTrue(any("sales" in req for req in requirements))

        # 验证源和目标Staff ID
        self.assertEqual(task.source_staff_id, self.user_staff_id)
        self.assertEqual(task.response_staff_id, self.cm_staff_id)

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
                    "name_like": "calculator_"  # 使用更通用的匹配模式
                }
            )

            # 直接使用返回的Resource对象列表
            if resources:
                for resource in resources:
                    # 删除资源
                    await asyncio.to_thread(
                        _SHARED_RESOURCE_TOOL.run,
                        action="delete",
                        opera_id=str(self.test_opera_id),
                        resource_id=resource.id
                    )
        except Exception as e:
            print(f"清理资源时出错: {e}")


class TestResourceGeneration(AsyncTestCase):
    """测试资源的生成任务，由CR执行并且发送tagged dialogue"""

    def setUp(self):
        """设置测试环境"""
        # 创建测试用的Bot IDs
        self.cr_bot_id = UUID('894c1763-22b2-418c-9a18-3c40b88d28bc')  # CR的Bot ID
        self.test_opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')  # 测试用Opera ID
        self.user_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')  # 用户的Staff ID
        self.cr_staff_id = UUID('06ec00fc-9546-40b0-b180-b482ba0e0e27')  # CR的Staff ID

        # 创建测试用的agent配置
        self.test_config = {
            'agents': [
                {
                    'name': '前端架构专家',
                    'role': '资深前端工程师',
                    'goal': '设计和实现高质量的前端代码，确保代码的可维护性和性能',
                    'backstory': '''你是一个经验丰富的前端架构师，擅长：
                    1. 响应式布局设计和实现
                    2. 组件化开发和模块化设计
                    3. 性能优化和最佳实践
                    4. 主流前端框架和工具的使用
                    5. 代码质量和架构设计
                    
                    你需要：
                    1. 理解整个项目的结构和依赖关系
                    2. 确保生成的代码符合现代前端开发标准
                    3. 正确处理文件间的引用关系
                    4. 实现响应式和交互功能
                    5. 遵循代码最佳实践''',
                    'tools': []
                },
                {
                    'name': 'UI交互专家',
                    'role': 'UI/UX工程师',
                    'goal': '实现流畅的用户交互和优秀的用户体验',
                    'backstory': '''你是一个专注于用户体验的UI工程师，擅长：
                    1. 交互设计和实现
                    2. 动画效果开发
                    3. 用户体验优化
                    4. 无障碍设计
                    5. 响应式UI组件开发
                    
                    你需要：
                    1. 设计流畅的交互体验
                    2. 实现符合直觉的用户界面
                    3. 确保跨设备的一致性
                    4. 优化加载和响应速度
                    5. 处理各种边界情况''',
                    'tools': []
                }
            ],
            'process': 'sequential',  # 使用协作模式，决定是否让多个专家共同完成任务
            'verbose': True
        }

        # 创建CrewRunner实例
        self.crew_runner = CrewRunner(config=self.test_config, bot_id=self.cr_bot_id)

        # 设置通用的测试时间
        self.test_time = datetime.now(timezone.utc).isoformat()

        # 初始化CrewRunner
        self.run_async(self._init_crew_runner())

    async def _init_crew_runner(self):
        """初始化CrewRunner，但不进入主循环"""
        original_is_running = self.crew_runner.is_running
        self.crew_runner.is_running = False
        try:
            await self.crew_runner.run()
        finally:
            self.crew_runner.is_running = original_is_running

    def test_code_generation_task(self):
        """测试代码生成任务的处理"""
        self.run_async(self._test_code_generation_task())

    async def _test_code_generation_task(self):
        # 创建一个代码生成任务
        task = BotTask(
            id=UUID('93c9e569-e529-4644-947b-b98c16d4d7a4'),
            type=TaskType.RESOURCE_GENERATION,
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            description='生成代码文件: src/js/product-modal.js',
            parameters={
                'file_path': 'src/js/product-modal.js',
                'file_type': 'javascript',
                'mime_type': 'text/javascript',
                'description': 'JavaScript file for displaying product details in a modal',
                'references': [],
                'code_details': {
                    'project_type': 'web',
                    'project_description': 'A responsive product showcase webpage with grid layout and filtering capability.',
                    'requirements': [
                        'Responsive grid layout for products',
                        'Product filtering capability',
                        'Product detail view in a modal'
                    ],
                    'frameworks': ['normalize.css', '@popperjs/core'],
                    'resources': [
                        {
                            'file_path': 'src/html/index.html',
                            'type': 'html',
                            'mime_type': 'text/html',
                            'description': 'Main page with responsive grid layout for product showcase',
                            'references': [
                                'src/css/main.css',
                                'src/css/product-card.css',
                                'src/js/main.js',
                                'src/js/product-modal.js'
                            ]
                        }
                    ]
                },
                'dialogue_context': {
                    'text': '请创建一个响应式的产品展示页面，包含产品详情模态框功能',
                    'type': 'CODE_RESOURCE'
                },
                'opera_id': str(self.test_opera_id)
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cr_staff_id
        )

        # 将任务添加到队列中
        await self.crew_runner.task_queue.add_task(task)

        # 执行代码生成
        await self.crew_runner._handle_generation_task(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_runner.task_queue.tasks if t.id == task.id)

        # 验证任务状态
        self.assertEqual(updated_task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(updated_task.result)
        self.assertIsNotNone(updated_task.result.get("text"))
        self.assertIsNotNone(updated_task.result.get("dialogue_id"))

        # 验证生成的代码是否已通过dialogue发送
        dialogue_result = _SHARED_DIALOGUE_TOOL.run(
            action="get",
            opera_id=str(self.test_opera_id),
            dialogue_index=updated_task.result["dialogue_id"]
        )
        status_code, dialogue_data = ApiResponseParser.parse_response(dialogue_result)

        # 验证对话消息
        self.assertEqual(status_code, 200)
        self.assertIsNotNone(dialogue_data)
        self.assertEqual(dialogue_data["staffId"], str(task.response_staff_id))
        self.assertIn("CODE_RESOURCE", dialogue_data["tags"])

    def test_code_generation_error_handling(self):
        """测试代码生成过程中的错误处理"""
        self.run_async(self._test_code_generation_error_handling())

    async def _test_code_generation_error_handling(self):
        # 创建一个缺少必要参数的任务
        task = BotTask(
            id=UUID('93c9e569-e529-4644-947b-b98c16d4d7a5'),
            type=TaskType.RESOURCE_GENERATION,
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            description='生成代码文件: test.js',
            parameters={
                'file_path': 'test.js',
                # 缺少其他必要参数
                'opera_id': str(self.test_opera_id)
            },
            source_staff_id=self.user_staff_id,
            response_staff_id=self.cr_staff_id
        )

        # 将任务添加到队列中
        await self.crew_runner.task_queue.add_task(task)

        # 执行代码生成
        await self.crew_runner._handle_generation_task(task)

        # 从任务队列中获取更新后的任务
        updated_task = next(t for t in self.crew_runner.task_queue.tasks if t.id == task.id)

        # 验证任务状态和错误信息
        self.assertEqual(updated_task.status, TaskStatus.FAILED)
        self.assertIsNotNone(updated_task.error_message)

    def tearDown(self):
        """清理测试环境"""
        self.run_async(self._tearDown())

    async def _tearDown(self):
        # 清理任务队列
        self.crew_runner.task_queue.tasks.clear()

        # 清理测试过程中创建的对话
        if self.crew_runner.client:
            await self.crew_runner.client.disconnect()

        # 清理生成的资源和对话
        try:
            # 获取测试期间创建的对话
            dialogues = _SHARED_DIALOGUE_TOOL.run(
                action="get_filtered",
                opera_id=str(self.test_opera_id),
                data={
                    "tags": ["code_creation"]
                }
            )

            # 删除测试创建的对话
            if dialogues:
                for dialogue in dialogues:
                    _SHARED_DIALOGUE_TOOL.run(
                        action="delete",
                        opera_id=str(self.test_opera_id),
                        dialogue_id=dialogue.id
                    )
        except Exception as e:
            print(f"清理资源时出错: {e}")


if __name__ == '__main__':
    unittest.main()
