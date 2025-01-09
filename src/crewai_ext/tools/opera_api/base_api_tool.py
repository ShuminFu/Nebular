"""提供基于HTTP的API工具基类，用于构建各种API集成工具。

该模块实现了一个通用的API工具基类，提供了标准化的HTTP请求处理功能，
支持JSON和二进制响应，可用于构建特定API的工具类。
"""

from typing import Optional, Dict, Any, Type, Literal, Set
import random
import time
import httpx
from pydantic import BaseModel, Field
from crewai_tools.tools.base_tool import BaseTool


class RetryConfig(BaseModel):
    """重试配置类"""
    max_retries: int = Field(default=3, description="最大重试次数")
    base_delay: float = Field(default=1.0, description="基础延迟时间(秒)")
    max_delay: float = Field(default=10.0, description="最大延迟时间(秒)")
    retry_codes: Set[int] = Field(
        default={408, 429, 500, 502, 503, 504},
        description="需要重试的HTTP状态码"
    )
    enable_jitter: bool = Field(default=True, description="是否启用随机抖动")


class BaseApiTool(BaseTool):
    """基础API工具类，提供通用的HTTP请求功能"""

    name: str = "Base API Tool"
    description: str = "Base class for API tools"
    args_schema: Type[BaseModel] = BaseModel
    base_url: str = ""  # 子类需要覆盖这个属性
    retry_config: RetryConfig = RetryConfig()

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
        retry_count = 0
        last_exception = None

        with httpx.Client() as client:
            while retry_count <= self.retry_config.max_retries:
                try:
                    response = client.request(method, url, json=json, params=params, content=content)

                    # 检查是否需要重试
                    if response.status_code in self.retry_config.retry_codes and retry_count < self.retry_config.max_retries:
                        raise httpx.HTTPError(f"Retryable status code: {response.status_code}")

                    response.raise_for_status()

                    if response_type == 'binary':
                        return {
                            'status_code': response.status_code,
                            'data': response.content,
                            'content_type': response.headers.get('content-type'),
                            'content_disposition': response.headers.get('content-disposition'),
                            'retry_count': retry_count
                        }
                    else:
                        return {
                            'status_code': response.status_code,
                            'data': response.json() if response.text else None,
                            'retry_count': retry_count
                        }

                except httpx.HTTPError as e:
                    last_exception = e
                    if retry_count == self.retry_config.max_retries:
                        break

                    # 计算延迟时间(指数退避 + 可选的随机抖动)
                    delay = min(
                        self.retry_config.base_delay * (2 ** retry_count),
                        self.retry_config.max_delay
                    )

                    # 添加随机抖动
                    if self.retry_config.enable_jitter:
                        delay *= (0.5 + random.random())

                    print(f"Request failed, retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{self.retry_config.max_retries})")
                    time.sleep(delay)
                    retry_count += 1

            # 如果所有重试都失败了，抛出最后一个异常
            raise last_exception

    def _run(self, *args, **kwargs) -> str:
        """BaseTool要求的抽象方法实现
        
        子类应该重写这个方法来实现具体的业务逻辑
        """
        raise NotImplementedError("Subclasses must implement _run method")
