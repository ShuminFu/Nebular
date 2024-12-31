import os
import re
from Opera.core.task_utils import BotTaskQueue, TaskStatus, BotTask
from ai_core.tools.opera_api.temp_file_api_tool import _SHARED_TEMP_FILE_TOOL
from ai_core.tools.opera_api.resource_api_tool import _SHARED_RESOURCE_TOOL, Resource
from Opera.FastAPI.models import ResourceForCreation
from Opera.core.dialogue.enums import MIME_TYPE_MAPPING
import asyncio


class CodeMonkey:
    """负责资源的验证与搬运"""

    def __init__(self, task_queue: BotTaskQueue, logger):
        self.task_queue = task_queue
        self.log = logger
        # 定义文件大小限制(100MB)
        self.max_file_size = 100 * 1024 * 1024

    def _validate_file_path(self, file_path: str) -> bool:
        """验证文件路径是否合法
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 路径是否合法
            
        Raises:
            ValueError: 当路径不合法时抛出异常
        """
        if not file_path:
            raise ValueError("文件路径不能为空")

        # 检查路径长度
        if len(file_path) > 255:
            raise ValueError("文件路径过长")

        # 检查是否包含非法字符
        illegal_chars = re.compile(r'[<>:"|?*\x00-\x1F]')
        if illegal_chars.search(file_path):
            raise ValueError("文件路径包含非法字符")

        # 检查目录穿越
        normalized_path = os.path.normpath(file_path)
        if normalized_path.startswith("..") or normalized_path.startswith("/"):
            raise ValueError("不允许目录穿越")

        return True

    def _validate_mime_type(self, mime_type: str, file_path: str) -> bool:
        """验证MIME类型是否合法且与文件扩展名匹配
        
        Args:
            mime_type: MIME类型
            file_path: 文件路径
            
        Returns:
            bool: MIME类型是否合法
            
        Raises:
            ValueError: 当MIME类型不合法时抛出异常
        """
        if not mime_type:
            raise ValueError("MIME类型不能为空")

        if mime_type not in MIME_TYPE_MAPPING:
            raise ValueError(f"不支持的MIME类型: {mime_type}")

        # 检查文件扩展名是否匹配
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in MIME_TYPE_MAPPING[mime_type]:
            raise ValueError(f"文件扩展名与MIME类型不匹配: {ext} vs {mime_type}")

        return True

    def _validate_code_content(self, code_content: str) -> bool:
        """验证代码内容是否合法
        
        Args:
            code_content: 代码内容
            
        Returns:
            bool: 内容是否合法
            
        Raises:
            ValueError: 当内容不合法时抛出异常
        """
        if not code_content:
            raise ValueError("代码内容不能为空")

        # 检查内容大小
        content_size = len(code_content.encode('utf-8'))
        if content_size > self.max_file_size:
            raise ValueError(f"代码内容超过大小限制: {content_size} > {self.max_file_size}")

        # 检查编码
        try:
            code_content.encode('utf-8').decode('utf-8')
        except UnicodeError:
            raise ValueError("代码内容必须是有效的UTF-8编码")

        return True

    async def handle_resource_creation(self, task: BotTask):
        """处理资源创建任务"""
        try:
            # 从任务参数中获取资源信息
            file_path = task.parameters.get("file_path")
            description = task.parameters.get("description")
            tags = task.parameters.get("tags", [])
            code_content = task.parameters.get("code_content")
            opera_id = task.parameters.get("opera_id")
            mime_type = task.parameters.get("mime_type", "text/plain")

            if not all([file_path, code_content, opera_id]):
                raise ValueError("缺少必要的资源信息")

            # 验证输入
            try:
                self._validate_file_path(file_path)
                self._validate_mime_type(mime_type, file_path)
                self._validate_code_content(code_content)
            except ValueError as e:
                raise ValueError(f"输入验证失败: {str(e)}")

            # 1. 先将代码内容上传为临时文件
            temp_file_result = await asyncio.to_thread(
                _SHARED_TEMP_FILE_TOOL.run,
                operation="upload",
                content=code_content.encode('utf-8')
            )
            if not isinstance(temp_file_result, str) or "成功上传临时文件" not in temp_file_result:
                raise Exception(f"上传临时文件失败: {temp_file_result}")

            # 从返回的消息中提取temp_file_id，格式为: '成功上传临时文件，ID: uuid, 长度: xx 字节'
            temp_file_id = temp_file_result.split("ID: ")[1].split(",")[0].strip()

            # 2. 创建资源
            resource_result = await asyncio.to_thread(
                _SHARED_RESOURCE_TOOL.run,
                action="create",
                opera_id=opera_id,
                data=ResourceForCreation(
                    name=file_path,
                    description=description,
                    mime_type=mime_type,
                    last_update_staff_name=str(task.response_staff_id),
                    temp_file_id=temp_file_id
                )
            )

            # 直接使用Resource对象
            if isinstance(resource_result, Resource):
                # 更新任务状态为完成
                await self.task_queue.update_task_status(
                    task_id=task.id,
                    new_status=TaskStatus.COMPLETED
                )
                # 设置任务结果
                task.result = {
                    "resource_id": str(resource_result.id),
                    "path": file_path,
                    "status": "success"
                }
                self.log.info(f"资源创建成功: {file_path}")
            else:
                raise Exception(f"资源创建失败: {resource_result}")

        except Exception as e:
            self.log.error(f"处理资源创建任务时发生错误: {str(e)}")
            # 更新任务状态为失败
            await self.task_queue.update_task_status(
                task_id=task.id,
                new_status=TaskStatus.FAILED
            )
            # 设置错误信息
            task.error_message = str(e)
            # 设置任务结果
            task.result = {
                "path": task.parameters.get("file_path"),
                "status": "failed",
                "error": str(e)
            }
