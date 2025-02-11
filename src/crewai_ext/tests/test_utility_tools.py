"""实用工具集的单元测试模块。

该模块包含对时间处理工具和UUID生成工具的全面测试用例。
"""

import re
import pytest
from datetime import datetime
from src.crewai_ext.tools.utils.utility_tools import CurrentTimeTool, UUIDGeneratorTool


class TestCurrentTimeTool:
    """时间工具测试类"""

    def setup_method(self):
        """测试前初始化"""
        self.time_tool = CurrentTimeTool()

    def test_default_format(self):
        """测试默认格式输出"""
        result = self.time_tool._run()
        # 验证格式是否符合 YYYY-MM-DD HH:MM:SS
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", result)

    def test_custom_format(self):
        """测试自定义格式输出"""
        custom_format = "%Y/%m/%d"
        result = self.time_tool._run(format=custom_format)
        # 验证格式是否符合 YYYY/MM/DD
        assert re.match(r"\d{4}/\d{2}/\d{2}", result)

    def test_timezone(self):
        """测试时区功能"""
        # 使用上海时区
        shanghai_result = self.time_tool._run(timezone="Asia/Shanghai")
        # 使用纽约时区
        ny_result = self.time_tool._run(timezone="America/New_York")

        # 转换为datetime对象进行比较
        shanghai_time = datetime.strptime(shanghai_result, "%Y-%m-%d %H:%M:%S")
        ny_time = datetime.strptime(ny_result, "%Y-%m-%d %H:%M:%S")

        # 验证两个时间点确实有时差
        assert shanghai_time != ny_time

    def test_invalid_format(self):
        """测试无效的格式字符串"""
        with pytest.raises(ValueError) as exc_info:
            self.time_tool._run(format="invalid")
        assert "Invalid time format" in str(exc_info.value)

    def test_invalid_timezone(self):
        """测试无效的时区"""
        with pytest.raises(ValueError) as exc_info:
            self.time_tool._run(timezone="Invalid/Timezone")
        assert "Invalid timezone" in str(exc_info.value)


class TestUUIDGeneratorTool:
    """UUID生成工具测试类"""

    def setup_method(self):
        """测试前初始化"""
        self.uuid_tool = UUIDGeneratorTool()

    def test_default_uuid4(self):
        """测试默认生成UUID4"""
        result = self.uuid_tool._run()
        # 验证UUID格式
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", result)

    def test_uuid1(self):
        """测试生成UUID1"""
        result = self.uuid_tool._run(version=1)
        # 验证UUID格式
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-1[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", result)

    def test_uuid3(self):
        """测试生成UUID3"""
        namespace = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"  # DNS namespace
        name = "test.example.com"
        result = self.uuid_tool._run(version=3, namespace=namespace, name=name)
        # 验证UUID格式
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-3[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", result)

    def test_uuid5(self):
        """测试生成UUID5"""
        namespace = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"  # DNS namespace
        name = "test.example.com"
        result = self.uuid_tool._run(version=5, namespace=namespace, name=name)
        # 验证UUID格式
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", result)

    def test_uuid3_deterministic(self):
        """测试UUID3的确定性"""
        namespace = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        name = "test.example.com"
        result1 = self.uuid_tool._run(version=3, namespace=namespace, name=name)
        result2 = self.uuid_tool._run(version=3, namespace=namespace, name=name)
        # 相同输入应产生相同的UUID
        assert result1 == result2

    def test_uuid5_deterministic(self):
        """测试UUID5的确定性"""
        namespace = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        name = "test.example.com"
        result1 = self.uuid_tool._run(version=5, namespace=namespace, name=name)
        result2 = self.uuid_tool._run(version=5, namespace=namespace, name=name)
        # 相同输入应产生相同的UUID
        assert result1 == result2

    def test_invalid_version(self):
        """测试无效的UUID版本"""
        with pytest.raises(ValueError) as exc_info:
            self.uuid_tool._run(version=2)
        assert "Unsupported UUID version" in str(exc_info.value)

    def test_missing_namespace_name(self):
        """测试缺少namespace和name参数"""
        with pytest.raises(ValueError) as exc_info:
            self.uuid_tool._run(version=3)
        assert "requires both namespace and name" in str(exc_info.value)

    def test_invalid_namespace(self):
        """测试无效的namespace"""
        with pytest.raises(ValueError) as exc_info:
            self.uuid_tool._run(version=3, namespace="invalid", name="test")
        assert "Invalid namespace UUID" in str(exc_info.value)
