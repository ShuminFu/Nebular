"""提供临时文件管理功能的API工具，支持文件的上传、追加和删除操作。"""

from typing import Optional, Type, ClassVar
from uuid import UUID
from pydantic import BaseModel, Field
from src.crewai_core.tools.opera_api.base_api_tool import BaseApiTool


class TempFileToolSchema(BaseModel):
    """临时文件操作参数模型"""
    operation: str = Field(
        ...,
        description="操作类型: 'upload' - 上传新文件（可选：追加到已有文件）, 'append' - 追加到已有文件, 'delete' - 删除文件"
    )
    temp_file_id: Optional[UUID] = Field(
        default=None,
        description="临时文件ID。upload时可选（指定则追加到已有文件），append和delete时必需"
    )
    content: Optional[bytes] = Field(
        default=None,
        description="文件数据块，upload和append操作时必需"
    )


class TempFileTool(BaseApiTool):
    """临时文件管理工具，用于上传、追加和删除临时文件"""

    name: str = "Temp File Tool"
    description: str = """用于管理临时文件的工具。
    支持以下操作：
    1. 上传新的临时文件或追加到已有文件
    2. 追加数据到已存在的临时文件
    3. 删除临时文件
    
    示例输入:
    1. 上传新文件: {
        'operation': 'upload',
        'content': b'文件内容'  # bytes类型
    }
    2. 追加到已有文件: {
        'operation': 'append',
        'temp_file_id': 'uuid',
        'content': b'追加的内容'  # bytes类型
    }
    3. 上传并指定文件ID: {
        'operation': 'upload',
        'temp_file_id': 'uuid',  # 可选，指定则追加到该文件
        'content': b'文件内容'  # bytes类型
    }
    4. 删除文件: {
        'operation': 'delete',
        'temp_file_id': 'uuid'
    }
    
    注意：
    - 临时文件在Opera重启时会被清空
    - 当临时文件被用作资源文件时会被移出临时目录
    """
    args_schema: Type[BaseModel] = TempFileToolSchema
    BASE_URL: ClassVar[str] = "http://opera.nti56.com/TempFile"

    def _run(self, *args, **kwargs) -> str:
        """执行临时文件操作

        Args:
            kwargs: 包含operation、temp_file_id和content的字典

        Returns:
            str: 操作结果描述
        """
        try:
            operation = kwargs.get("operation")
            temp_file_id = kwargs.get("temp_file_id")
            content = kwargs.get("content")

            if operation == "upload":
                if not content:
                    raise ValueError("上传操作需要提供文件数据")
                url = self.BASE_URL
                if temp_file_id:
                    url = f"{url}?id={temp_file_id}"
                response = self._make_request(
                    method="POST",
                    url=url,
                    content=content
                )
                result = response['data']
                return f"成功上传临时文件，ID: {result['id']}, 长度: {result['length']} 字节"

            elif operation == "append":
                if not temp_file_id:
                    raise ValueError("追加操作需要提供临时文件ID")
                if not content:
                    raise ValueError("追加操作需要提供文件数据")
                response = self._make_request(
                    method="POST",
                    url=f"{self.BASE_URL}/{temp_file_id}",
                    content=content
                )
                result = response['data']
                return f"成功追加数据到临时文件，ID: {result['id']}, 当前总长度: {result['length']} 字节"

            elif operation == "delete":
                if not temp_file_id:
                    raise ValueError("删除操作需要提供临时文件ID")
                self._make_request(
                    method="DELETE",
                    url=f"{self.BASE_URL}/{temp_file_id}"
                )
                return f"成功删除临时文件，ID: {temp_file_id}"

            else:
                raise ValueError(f"不支持的操作类型: {operation}")

        except Exception as e:
            return f"操作失败: {str(e)}"

    def _process_response(self, response: dict) -> str:
        """处理API响应

        Args:
            response: API响应数据

        Returns:
            str: 处理后的响应消息
        """
        if response['status_code'] == 204:  # 删除操作成功
            return "操作成功"
        return str(response['data'])


_SHARED_TEMP_FILE_TOOL = TempFileTool()
