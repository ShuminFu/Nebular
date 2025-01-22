import requests
from functools import lru_cache
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class UrlService:
    def __init__(self, base_url: str, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.session = requests.Session()

    @lru_cache(maxsize=128)
    def get_cached_response(self, endpoint: str) -> Dict[str, Any]:
        """使用缓存获取URL响应"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.info(f"Fetching cached response from: {url}")
        return self._make_request(url)

    def _make_request(self, url: str) -> Dict[str, Any]:
        """执行实际的HTTP请求，带重试机制"""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                return {"status_code": response.status_code, "data": response.json()}
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise


class ApiClient:
    def __init__(self, service: UrlService):
        self.service = service

    def fetch_endpoint_status(self, endpoint: str) -> int:
        """通过服务获取端点状态"""
        try:
            result = self.service.get_cached_response(endpoint)
            return result["status_code"]
        except Exception as e:
            logger.error(f"Error fetching endpoint status: {str(e)}")
            raise
