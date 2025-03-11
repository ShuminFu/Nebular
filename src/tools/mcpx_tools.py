from typing import List, Type, Optional, Dict, Any
from pydantic import BaseModel, create_model
from crewai.tools import BaseTool
from mcp_run import Client
import json

from crewai import LLM

# 基础配置
llm = LLM(model="deepseek-r1")

# 高级配置与详细参数
llm = LLM(
    model="deepseek-r1",
    temperature=0.7,  # 更高的值产生更有创意的输出
    timeout=120,  # 等待响应的秒数
    max_tokens=4000,  # 响应的最大长度
    top_p=0.9,  # 核采样参数
    frequency_penalty=0.1,  # 减少重复
    presence_penalty=0.1,  # 鼓励主题多样性
    response_format={"type": "json"},  # 用于结构化输出
    seed=42,  # 用于可重现的结果
)


class MCPTool(BaseTool):
    """用于CrewAI的mcp.run工具包装器。"""

    name: str
    description: str
    _client: Client
    _tool_name: str

    def _run(self, text: Optional[str] = None, **kwargs) -> str:
        """使用提供的参数执行mcp.run工具。"""

        try:
            if text:
                try:
                    input_dict = json.loads(text)
                except json.JSONDecodeError:
                    input_dict = {"text": text}
            else:
                input_dict = kwargs

            # 使用输入参数调用mcp.run工具
            results = self._client.call(self._tool_name, input=input_dict)

            output = []
            for content in results.content:
                if content.type == "text":
                    output.append(content.text)
            return "\n".join(output)
        except Exception as e:
            raise RuntimeError(f"MCPX工具执行失败: {str(e)}")


def get_mcprun_tools(session_id: Optional[str] = None) -> List[BaseTool]:
    """从已安装的mcp.run工具创建CrewAI工具。"""
    client = Client(session_id=session_id)
    crew_tools = []

    for tool_name, tool in client.tools.items():
        # 从模式创建Pydantic模型
        args_schema = _convert_json_schema_to_pydantic(tool.input_schema, f"{tool_name}Schema")

        # 使用转换后的模式创建CrewAI工具
        crew_tool = MCPTool(
            name=tool_name,
            description=tool.description,
            args_schema=args_schema,
        )

        crew_tool._client = client
        crew_tool._tool_name = tool_name

        crew_tools.append(crew_tool)

    return crew_tools


def _convert_json_schema_to_pydantic(schema: Dict[str, Any], model_name: str = "DynamicModel") -> Type[BaseModel]:
    """将JSON模式字典转换为Pydantic模型。"""
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    fields = {}
    for field_name, field_schema in properties.items():
        field_type = _get_field_type(field_schema)

        # 正确处理默认值
        default = field_schema.get("default", None)
        if field_name in required:
            # 必需字段没有默认值
            fields[field_name] = (field_type, ...)
        else:
            # 可选字段，有或没有默认值
            fields[field_name] = (Optional[field_type], default)

    return create_model(model_name, **fields)


def _get_field_type(field_schema: Dict[str, Any]) -> Type:
    """将JSON模式类型转换为Python类型。"""
    schema_type = field_schema.get("type", "string")

    if schema_type == "array":
        items = field_schema.get("items", {})
        item_type = _get_field_type(items)
        return List[item_type]

    elif schema_type == "object":
        # 通过创建新模型处理嵌套对象
        return _convert_json_schema_to_pydantic(field_schema, "NestedModel")

    # 基本类型映射
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }
    return type_mapping.get(schema_type, str)


if __name__ == "__main__":
    mcpx_tools = get_mcprun_tools()
    print(mcpx_tools)
