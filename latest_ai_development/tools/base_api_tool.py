from typing import Optional, Dict, Any
import httpx
from crewai_tools.tools.base_tool import BaseTool


class BaseApiTool(BaseTool):
    """基础API工具类，提供通用的HTTP请求功能"""
    
    base_url: str = ""  # 子类需要覆盖这个属性
    
    def _make_request(self, method: str, url: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> dict:
        """发送HTTP请求的通用方法
        
        Args:
            method: HTTP方法（GET, POST, PUT, DELETE等）
            url: 请求URL
            json: 请求体数据（可选）
            params: URL参数（可选）
            
        Returns:
            dict: 包含响应数据和状态码的字典
        """
        with httpx.Client() as client:
            response = client.request(method, url, json=json, params=params)
            response.raise_for_status()
            return {
                'status_code': response.status_code,
                'data': response.json() if response.text else None
            } 