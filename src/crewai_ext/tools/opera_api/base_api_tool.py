"""提供基于HTTP的API工具基类，用于构建各种API集成工具。

该模块实现了一个通用的API工具基类，提供了标准化的HTTP请求处理功能，
支持JSON和二进制响应，可用于构建特定API的工具类。
"""

from typing import Optional, Dict, Any, Type, Literal
import httpx
from pydantic import BaseModel
from crewai_tools.tools.base_tool import BaseTool


class BaseApiTool(BaseTool):
    """基础API工具类，提供通用的HTTP请求功能"""

    name: str = "Base API Tool"
    description: str = "Base class for API tools"
    args_schema: Type[BaseModel] = BaseModel
    base_url: str = ""  # 子类需要覆盖这个属性

    def _make_request(self, method: str, url: str, json: Optional[Dict[str, Any]] = None,
                      params: Optional[Dict[str, Any]] = None, 
                      content: Optional[bytes] = None,
                      response_type: Literal['json', 'binary'] = 'json') -> dict:
        """发送HTTP请求的通用方法

        Args:
            method: HTTP方法（GET, POST, PUT, DELETE等）
            url: 请求URL
            json: 请求体数据（可选）
            params: URL参数（可选）
            content: 原始二进制内容（可选）
            response_type: 响应类型，'json'用于JSON响应，'binary'用于文件流响应

        Returns:
            dict: 包含响应数据和状态码的字典。
                 对于JSON响应，返回解析后的JSON数据
                 对于二进制响应，返回原始字节数据
        """
        with httpx.Client() as client:
            response = client.request(method, url, json=json, params=params, content=content)
            response.raise_for_status()
            
            if response_type == 'binary':
                return {
                    'status_code': response.status_code,
                    'data': response.content,
                    'content_type': response.headers.get('content-type'),
                    'content_disposition': response.headers.get('content-disposition')
                }
            else:
                return {
                    'status_code': response.status_code,
                    'data': response.json() if response.text else None
                }

    def _run(self, *args, **kwargs) -> str:
        """BaseTool要求的抽象方法实现
        
        子类应该重写这个方法来实现具体的业务逻辑
        """
        raise NotImplementedError("Subclasses must implement _run method")
