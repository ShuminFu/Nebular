"""提供实用工具集，包含时间处理、UUID生成等通用功能。

该模块实现了一系列实用工具类，提供了标准化的时间处理、UUID生成等功能，
可用于各种场景的基础操作。
"""

from datetime import datetime
import uuid
import re
from typing import Optional, Type, Literal, Set
from zoneinfo import ZoneInfo, available_timezones
from pydantic import BaseModel, Field
from crewai.tools.base_tool import BaseTool


class TimeFormatSchema(BaseModel):
    """时间格式化参数模型"""

    format: str = Field(default="%Y-%m-%d %H:%M:%S", description="时间格式化字符串，默认为'%Y-%m-%d %H:%M:%S'")
    timezone: Optional[str] = Field(default=None, description="时区名称，如'Asia/Shanghai'。默认使用系统时区")


class CurrentTimeTool(BaseTool):
    """获取当前时间的工具类"""

    name: str = "Current Time Tool"
    description: str = "获取当前时间，支持自定义格式和时区"
    args_schema: Type[BaseModel] = TimeFormatSchema

    # 有效的时间格式指令集合
    VALID_DIRECTIVES: Set[str] = {
        "%Y",
        "%m",
        "%d",
        "%H",
        "%M",
        "%S",  # 基本时间组件
        "%I",
        "%p",  # 12小时制
        "%B",
        "%b",
        "%A",
        "%a",  # 月份和星期的名称
        "%j",
        "%U",
        "%W",  # 年中的日和周
        "%z",
        "%Z",  # 时区
        "%c",
        "%x",
        "%X",  # 本地化的日期和时间表示
        "%f",
        "%y",  # 微秒和两位数年份
        "%%",  # 字面量 %
    }

    def _validate_format(self, format: str) -> None:
        """验证时间格式字符串

        Args:
            format: 时间格式化字符串

        Raises:
            ValueError: 当格式字符串无效时抛出
        """
        if not format:
            raise ValueError("Time format string cannot be empty")

        # 提取所有的格式指令
        directives = re.findall(r"%[a-zA-Z%]", format)

        # 检查是否有任何格式指令
        if not directives:
            raise ValueError(f"Invalid time format: {format} (no valid directives found)")

        # 验证每个指令
        for directive in directives:
            if directive not in self.VALID_DIRECTIVES:
                raise ValueError(f"Invalid time format: {format} (invalid directive: {directive})")

        try:
            # 使用一个固定的时间来验证格式
            test_time = datetime(2000, 1, 1)
            test_time.strftime(format)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid time format: {format}")

    def _run(self, format: str = "%Y-%m-%d %H:%M:%S", timezone: Optional[str] = None) -> str:
        """获取当前时间

        Args:
            format: 时间格式化字符串
            timezone: 时区名称，如果不指定则使用系统时区

        Returns:
            str: 格式化后的时间字符串

        Raises:
            ValueError: 当指定的时区无效或格式字符串无效时抛出
        """
        # 验证格式字符串
        self._validate_format(format)

        try:
            if timezone:
                if timezone not in available_timezones():
                    raise ValueError(f"Invalid timezone: {timezone}")
                tz = ZoneInfo(timezone)
                current_time = datetime.now(tz)
            else:
                current_time = datetime.now()

            return current_time.strftime(format)
        except ValueError as e:
            raise ValueError(f"Error formatting time: {str(e)}")


class UUIDSchema(BaseModel):
    """UUID生成参数模型"""

    version: Literal[1, 3, 4, 5] = Field(default=4, description="UUID版本(1, 3, 4, 5)，默认为4")
    namespace: Optional[str] = Field(default=None, description="用于版本3和版本5的命名空间UUID字符串")
    name: Optional[str] = Field(default=None, description="用于版本3和版本5的名称字符串")


class UUIDGeneratorTool(BaseTool):
    """UUID生成工具类"""

    name: str = "UUID Generator Tool"
    description: str = "生成UUID，支持版本1、3、4、5"
    args_schema: Type[BaseModel] = UUIDSchema

    def _run(self, version: Literal[1, 3, 4, 5] = 4, namespace: Optional[str] = None, name: Optional[str] = None) -> str:
        """生成UUID

        Args:
            version: UUID版本(1, 3, 4, 5)
            namespace: 用于版本3和版本5的命名空间UUID
            name: 用于版本3和版本5的名称

        Returns:
            str: 生成的UUID字符串

        Raises:
            ValueError: 当参数组合无效时抛出
        """
        try:
            if version == 1:
                return str(uuid.uuid1())
            elif version == 4:
                return str(uuid.uuid4())
            elif version in (3, 5):
                if not namespace or not name:
                    raise ValueError(f"Version {version} requires both namespace and name")
                try:
                    namespace_uuid = uuid.UUID(namespace)
                except ValueError:
                    raise ValueError(f"Invalid namespace UUID: {namespace}")

                if version == 3:
                    return str(uuid.uuid3(namespace_uuid, name))
                else:  # version 5
                    return str(uuid.uuid5(namespace_uuid, name))
            else:
                raise ValueError(f"Unsupported UUID version: {version}")
        except Exception as e:
            raise ValueError(f"Error generating UUID: {str(e)}")
