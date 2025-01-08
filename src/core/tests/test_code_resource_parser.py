import unittest
from src.core.code_resource_parser import CodeResourceParser


class TestCodeResourceParser(unittest.TestCase):
    """测试代码资源解析器的各种情况"""

    def test_parse_markdown_style(self):
        """测试Markdown风格的代码块解析"""
        content = '''```javascript
@file: src/js/app.js
@description: Main application logic
@tags: framework_react, ui_component
@version: 1.0.0
---
import React from 'react';

function App() {
    return <div>Hello World</div>;
}

export default App;
```'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证元数据
        self.assertEqual(metadata["file"], "src/js/app.js")
        self.assertEqual(metadata["description"], "Main application logic")
        self.assertEqual(metadata["tags"], ["framework_react", "ui_component"])
        self.assertEqual(metadata["version"], "1.0.0")

        # 验证代码内容
        self.assertIn("import React from 'react'", code)
        self.assertIn("export default App", code)

    def test_parse_jsdoc_style(self):
        """测试JSDoc风格的注释解析"""
        content = '''```javascript
/**
 * @file: src/js/utils.js
 * @description: Utility functions for the application
 * @tags: utils, helpers
 * @version: 1.0.0
 */

export function formatDate(date) {
    return date.toISOString();
}
```'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证元数据
        self.assertEqual(metadata["file"], "src/js/utils.js")
        self.assertEqual(metadata["description"], "Utility functions for the application")
        self.assertEqual(metadata["tags"], ["utils", "helpers"])

        # 验证代码内容
        self.assertIn("export function formatDate", code)
        self.assertNotIn("@file", code)

    def test_parse_no_metadata(self):
        """测试没有元数据的代码解析"""
        content = '''```python
def hello_world():
    print("Hello, World!")
```'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证元数据为空
        self.assertEqual(metadata, {})

        # 验证代码内容
        self.assertIn('def hello_world():', code)
        self.assertIn('print("Hello, World!")', code)

    def test_parse_with_trailing_description(self):
        """测试带有尾部描述的代码解析"""
        content = '''```javascript
@file: src/js/component.js
@description: A reusable component
---
export class MyComponent {
    render() {}
}
```

This component implements a reusable UI element with the following features...'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证元数据
        self.assertEqual(metadata["file"], "src/js/component.js")

        # 验证代码内容不包含尾部描述
        self.assertIn("export class MyComponent", code)
        self.assertNotIn("This component implements", code)

    def test_parse_complex_metadata(self):
        """测试复杂元数据的解析"""
        content = '''```typescript
@file: src/components/DataGrid.tsx
@description: Advanced data grid component with sorting and filtering
@tags: [ui_component, data_visualization, interactive, framework_react]
@version: 2.1.0
@dependencies: [@material-ui/core, @material-ui/icons]
@author: John Doe
---
import React from 'react';
import { DataGrid } from '@material-ui/data-grid';

export function MyDataGrid() {
    return <DataGrid />;
}
```'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证复杂元数据
        self.assertEqual(metadata["file"], "src/components/DataGrid.tsx")
        self.assertEqual(len(metadata["tags"]), 4)
        self.assertEqual(metadata["dependencies"], ["@material-ui/core", "@material-ui/icons"])

        # 验证代码内容
        self.assertIn("import React from 'react'", code)

    def test_parse_multiline_jsdoc_description(self):
        """测试多行JSDoc描述的解析"""
        content = '''```javascript
/**
 * @file: src/js/complex.js
 * @description: This is a complex component
 *              that spans multiple lines
 *              and has detailed documentation
 * @tags: [complex, multiline]
 */
class ComplexComponent {
    constructor() {}
}
```'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证多行描述
        self.assertTrue(metadata["description"].startswith("This is a complex component"))
        self.assertIn("spans multiple lines", metadata["description"])

        # 验证代码内容
        self.assertIn("class ComplexComponent", code)

    def test_parse_no_code_block_markers(self):
        """测试没有代码块标记的解析"""
        content = '''@file: src/js/simple.js
@description: Simple module
---
export const simple = true;'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证基本解析
        self.assertEqual(metadata["file"], "src/js/simple.js")
        self.assertIn("export const simple = true", code)

    def test_parse_with_empty_lines(self):
        """测试包含空行的代码解析"""
        content = '''```python
@file: src/utils/helpers.py
@description: Helper functions

---

def helper_function():
    """Helper function"""
    pass

# Empty line above and below

def another_helper():
    pass
```'''
        metadata, code = CodeResourceParser.parse(content)

        # 验证代码内容保留了空行
        self.assertIn("\n\n", code)
        self.assertIn("def helper_function()", code)
        self.assertIn("def another_helper()", code)

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试空内容
        metadata, code = CodeResourceParser.parse("")
        self.assertEqual(metadata, {})
        self.assertEqual(code, "")

        # 测试只有元数据没有代码
        content = '''```
@file: src/empty.js
@description: Empty file
---
```'''
        metadata, code = CodeResourceParser.parse(content)
        self.assertEqual(metadata["file"], "src/empty.js")
        self.assertEqual(code.strip(), "")

        # 测试只有代码没有元数据
        content = '''```
console.log("Hello");
```'''
        metadata, code = CodeResourceParser.parse(content)
        self.assertEqual(metadata, {})
        self.assertIn('console.log("Hello")', code)


if __name__ == '__main__':
    unittest.main()
