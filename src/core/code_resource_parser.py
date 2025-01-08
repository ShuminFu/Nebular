"""代码资源解析器模块

提供代码资源的解析功能，支持以下格式：
1. Markdown风格的代码块
2. JSDoc风格的注释
3. 直接代码格式
"""

import re
from typing import Dict, List, Optional, Union, Set, Tuple


class CodeResourceParser:
    """代码资源解析器类"""

    @staticmethod
    def parse(content: str) -> Tuple[Dict, str]:
        """解析代码资源内容
        
        支持的格式：
        1. Markdown代码块格式：
           ```language
           @file: path/to/file
           @description: description
           ---
           code
           ```
           
        2. JSDoc注释格式：
           ```language
           /**
            * @file: path/to/file
            * @description: description
            */
           code
           ```
           
        3. 直接代码格式（无元数据）：
           ```language
           code
           ```
        
        Args:
            content: 原始消息内容
            
        Returns:
            Tuple[Dict, str]: (元数据字典, 代码内容)
        """
        metadata = {}
        lines = content.split("\n")
        code_start = 0
        code_end = len(lines)

        # 移除可能的语言标记
        if lines and lines[0].strip().startswith("```"):
            code_start = 1

        # 检查是否有JSDoc风格的注释
        if code_start < len(lines) and lines[code_start].strip().startswith("/**"):
            in_jsdoc = True
            current_key = None
            current_value = []

            # 解析JSDoc注释中的元数据
            for i in range(code_start, len(lines)):
                line = lines[i].strip()
                if line.startswith("*/"):
                    # 如果有未处理完的键值对，保存它
                    if current_key and current_value:
                        metadata[current_key] = " ".join(current_value)
                    code_start = i + 1
                    break

                # 提取@标记的元数据，处理可能的*前缀
                line = line.lstrip("* ")
                if line.startswith("@"):
                    # 如果有未处理完的键值对，保存它
                    if current_key and current_value:
                        metadata[current_key] = " ".join(current_value)

                    try:
                        key, value = line[1:].split(":", 1)
                        current_key = key.strip()
                        current_value = [value.strip()]
                    except ValueError:
                        continue
                elif current_key and line:  # 如果有当前键且行不为空，则为多行值
                    current_value.append(line)
        else:
            # 检查是否有独立的元数据部分
            in_metadata = True
            current_key = None
            current_value = []

            for i in range(code_start, len(lines)):
                line = lines[i].strip()
                if line == "---":
                    # 如果有未处理完的键值对，保存它
                    if current_key and current_value:
                        metadata[current_key] = " ".join(current_value)
                    code_start = i + 1
                    break

                if line.startswith("@"):
                    # 如果有未处理完的键值对，保存它
                    if current_key and current_value:
                        metadata[current_key] = " ".join(current_value)

                    try:
                        key, value = line[1:].split(":", 1)
                        current_key = key.strip()
                        current_value = [value.strip()]
                    except ValueError:
                        continue
                elif current_key and line:  # 如果有当前键且行不为空，则为多行值
                    current_value.append(line)

        # 查找代码块的结束
        for i in range(code_start, len(lines)):
            if lines[i].strip() == "```":
                code_end = i
                break

        # 提取代码内容
        code = "\n".join(lines[code_start:code_end]).strip()

        # 清理metadata中的值
        for key in metadata:
            value = metadata[key]
            # 移除可能的引号和方括号
            value = value.strip('"\'[]')
            # 处理逗号分隔的列表
            if "," in value:
                value = [item.strip() for item in value.split(",")]
            metadata[key] = value

        return metadata, code
