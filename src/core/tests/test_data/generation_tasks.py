"""测试数据模块

此模块包含用于测试的generation tasks数据。
数据以字典形式存储,可以直接用于重建BotTask对象。
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID
from src.core.task_utils import BotTask, TaskType, TaskStatus, TaskPriority

# 测试时间基准点
TEST_TIME = datetime(2025, 1, 8, 10, 55, 22, tzinfo=timezone(timedelta(seconds=28800)))

# Bot和Staff IDs
BOT_IDS = {
    'cm_bot_id': UUID('4a4857d6-4664-452e-a37c-80a628ca28a0'),
    'cr_bot_id': UUID('894c1763-22b2-418c-9a18-3c40b88d28bc')
}

STAFF_IDS = {
    'user_staff_id': UUID('c2a71833-4403-4d08-8ef6-23e6327832b2'),
    'cm_staff_id': UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc'),
    'cr_staff_id': UUID('06ec00fc-9546-40b0-b180-b482ba0e0e27')
}

OPERA_ID = UUID('96028f82-9f76-4372-976c-f0c5a054db79')

# 生成任务数据
GENERATION_TASKS = [
    {
        'id': UUID('938a2657-0d48-43a5-a8d2-980afa8c60fe'),
        'created_at': TEST_TIME.replace(microsecond=270711),
        'started_at': TEST_TIME.replace(microsecond=402306),
        'completed_at': None,
        'priority': 3,  # TaskPriority.HIGH
        'type': 51,    # TaskType.RESOURCE_GENERATION
        'status': 3,   # TaskStatus.COMPLETED
        'description': '生成代码文件: src/js/product-modal.js',
        'parameters': {
            'file_path': 'src/js/product-modal.js',
            'file_type': 'javascript',
            'mime_type': 'text/javascript',
            'description': 'Script for displaying product details in a modal.',
            'references': [],
            'code_details': {
                'project_type': 'web',
                'project_description': 'Responsive product showcase webpage with filtering functionality and modal product details display.',
                'requirements': [
                    'Responsive grid layout for product display',
                    'Product filtering functionality',
                    'Product details modal implementation'
                ],
                'frameworks': ['normalize.css', '@popperjs/core'],
                'resources': [
                    {
                        'file_path': 'src/html/index.html',
                        'type': 'html',
                        'mime_type': 'text/html',
                        'description': 'Main page file with responsive grid layout to display products.',
                        'references': [
                            'src/css/main.css',
                            'src/css/product-card.css',
                            'src/js/main.js',
                            'src/js/product-modal.js'
                        ]
                    },
                    {
                        'file_path': 'src/css/main.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Main stylesheet for responsive layouts.'
                    },
                    {
                        'file_path': 'src/css/product-card.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Stylesheet for product card design.'
                    },
                    {
                        'file_path': 'src/js/main.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Main script implementing product filtering.'
                    },
                    {
                        'file_path': 'src/js/product-modal.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Script for displaying product details in a modal.'
                    }
                ]
            },
            'dialogue_context': {
                'text': '''请创建一个响应式的产品展示页面，包含以下功能：
            1. 主页面(index.html)：
               - 响应式网格布局展示产品
               - 产品过滤功能
            2. 样式文件：
               - 主样式(main.css)：响应式布局
               - 产品卡片样式(product-card.css)
            3. JavaScript文件：
               - 主逻辑(main.js)：实现产品过滤
               - 模态框(product-modal.js)：产品详情展示
            4. 依赖：
               - normalize.css用于样式重置
               - @popperjs/core用于模态框定位''',
                'type': 'CODE_RESOURCE',
                'tags': 'code_request,code_type_css,code_type_html,code_type_javascript,framework_normalize.css,framework_@popperjs/core'
            },
            'opera_id': str(OPERA_ID)
        },
        'source_dialogue_index': 1,
        'response_staff_id': STAFF_IDS['cm_staff_id'],
        'source_staff_id': STAFF_IDS['user_staff_id'],
        'progress': 0,
        'result': {'dialogue_id': 78, 'status': 'success'},
        'error_message': None,
        'retry_count': 0,
        'last_retry_at': None
    },
    {
        'id': UUID('302d8993-8957-4e82-b94c-f5ae43c50c63'),
        'created_at': TEST_TIME.replace(microsecond=269809),
        'started_at': TEST_TIME.replace(second=27, microsecond=427387),
        'completed_at': None,
        'priority': 3,  # TaskPriority.HIGH
        'type': 51,    # TaskType.RESOURCE_GENERATION
        'status': 3,   # TaskStatus.COMPLETED
        'description': '生成代码文件: src/js/main.js',
        'parameters': {
            'file_path': 'src/js/main.js',
            'file_type': 'javascript',
            'mime_type': 'text/javascript',
            'description': 'Main script implementing product filtering.',
            'references': [],
            'code_details': {
                'project_type': 'web',
                'project_description': 'Responsive product showcase webpage with filtering functionality and modal product details display.',
                'requirements': [
                    'Responsive grid layout for product display',
                    'Product filtering functionality',
                    'Product details modal implementation'
                ],
                'frameworks': ['normalize.css', '@popperjs/core'],
                'resources': [
                    {
                        'file_path': 'src/html/index.html',
                        'type': 'html',
                        'mime_type': 'text/html',
                        'description': 'Main page file with responsive grid layout to display products.',
                        'references': [
                            'src/css/main.css',
                            'src/css/product-card.css',
                            'src/js/main.js',
                            'src/js/product-modal.js'
                        ]
                    },
                    {
                        'file_path': 'src/css/main.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Main stylesheet for responsive layouts.'
                    },
                    {
                        'file_path': 'src/css/product-card.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Stylesheet for product card design.'
                    },
                    {
                        'file_path': 'src/js/main.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Main script implementing product filtering.'
                    },
                    {
                        'file_path': 'src/js/product-modal.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Script for displaying product details in a modal.'
                    }
                ]
            },
            'dialogue_context': {
                'text': '''请创建一个响应式的产品展示页面，包含以下功能：
            1. 主页面(index.html)：
               - 响应式网格布局展示产品
               - 产品过滤功能
            2. 样式文件：
               - 主样式(main.css)：响应式布局
               - 产品卡片样式(product-card.css)
            3. JavaScript文件：
               - 主逻辑(main.js)：实现产品过滤
               - 模态框(product-modal.js)：产品详情展示
            4. 依赖：
               - normalize.css用于样式重置
               - @popperjs/core用于模态框定位''',
                'type': 'CODE_RESOURCE',
                'tags': 'code_request,code_type_css,code_type_html,code_type_javascript,framework_normalize.css,framework_@popperjs/core'
            },
            'opera_id': str(OPERA_ID)
        },
        'source_dialogue_index': 1,
        'response_staff_id': STAFF_IDS['cm_staff_id'],
        'source_staff_id': STAFF_IDS['user_staff_id'],
        'progress': 0,
        'result': {'dialogue_id': 80, 'status': 'success'},
        'error_message': None,
        'retry_count': 0,
        'last_retry_at': None
    },
    {
        'id': UUID('362b7b12-633a-4677-818c-4970325c49c6'),
        'created_at': TEST_TIME.replace(microsecond=269253),
        'started_at': TEST_TIME.replace(second=27, microsecond=535638),
        'completed_at': None,
        'priority': 3,  # TaskPriority.HIGH
        'type': 51,    # TaskType.RESOURCE_GENERATION
        'status': 3,   # TaskStatus.COMPLETED
        'description': '生成代码文件: src/css/product-card.css',
        'parameters': {
            'file_path': 'src/css/product-card.css',
            'file_type': 'css',
            'mime_type': 'text/css',
            'description': 'Stylesheet for product card design.',
            'references': [],
            'code_details': {
                'project_type': 'web',
                'project_description': 'Responsive product showcase webpage with filtering functionality and modal product details display.',
                'requirements': [
                    'Responsive grid layout for product display',
                    'Product filtering functionality',
                    'Product details modal implementation'
                ],
                'frameworks': ['normalize.css', '@popperjs/core'],
                'resources': [
                    {
                        'file_path': 'src/html/index.html',
                        'type': 'html',
                        'mime_type': 'text/html',
                        'description': 'Main page file with responsive grid layout to display products.',
                        'references': [
                            'src/css/main.css',
                            'src/css/product-card.css',
                            'src/js/main.js',
                            'src/js/product-modal.js'
                        ]
                    },
                    {
                        'file_path': 'src/css/main.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Main stylesheet for responsive layouts.'
                    },
                    {
                        'file_path': 'src/css/product-card.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Stylesheet for product card design.'
                    },
                    {
                        'file_path': 'src/js/main.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Main script implementing product filtering.'
                    },
                    {
                        'file_path': 'src/js/product-modal.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Script for displaying product details in a modal.'
                    }
                ]
            },
            'dialogue_context': {
                'text': '''请创建一个响应式的产品展示页面，包含以下功能：
            1. 主页面(index.html)：
               - 响应式网格布局展示产品
               - 产品过滤功能
            2. 样式文件：
               - 主样式(main.css)：响应式布局
               - 产品卡片样式(product-card.css)
            3. JavaScript文件：
               - 主逻辑(main.js)：实现产品过滤
               - 模态框(product-modal.js)：产品详情展示
            4. 依赖：
               - normalize.css用于样式重置
               - @popperjs/core用于模态框定位''',
                'type': 'CODE_RESOURCE',
                'tags': 'code_request,code_type_css,code_type_html,code_type_javascript,framework_normalize.css,framework_@popperjs/core'
            },
            'opera_id': str(OPERA_ID)
        },
        'source_dialogue_index': 1,
        'response_staff_id': STAFF_IDS['cm_staff_id'],
        'source_staff_id': STAFF_IDS['user_staff_id'],
        'progress': 0,
        'result': {'dialogue_id': 82, 'status': 'success'},
        'error_message': None,
        'retry_count': 0,
        'last_retry_at': None
    },
    {
        'id': UUID('ebed7b64-0895-4b17-ae09-3b54493c5405'),
        'created_at': TEST_TIME.replace(microsecond=268717),
        'started_at': TEST_TIME.replace(second=27, microsecond=627570),
        'completed_at': None,
        'priority': 3,  # TaskPriority.HIGH
        'type': 51,    # TaskType.RESOURCE_GENERATION
        'status': 3,   # TaskStatus.COMPLETED
        'description': '生成代码文件: src/css/main.css',
        'parameters': {
            'file_path': 'src/css/main.css',
            'file_type': 'css',
            'mime_type': 'text/css',
            'description': 'Main stylesheet for responsive layouts.',
            'references': [],
            'code_details': {
                'project_type': 'web',
                'project_description': 'Responsive product showcase webpage with filtering functionality and modal product details display.',
                'requirements': [
                    'Responsive grid layout for product display',
                    'Product filtering functionality',
                    'Product details modal implementation'
                ],
                'frameworks': ['normalize.css', '@popperjs/core'],
                'resources': [
                    {
                        'file_path': 'src/html/index.html',
                        'type': 'html',
                        'mime_type': 'text/html',
                        'description': 'Main page file with responsive grid layout to display products.',
                        'references': [
                            'src/css/main.css',
                            'src/css/product-card.css',
                            'src/js/main.js',
                            'src/js/product-modal.js'
                        ]
                    },
                    {
                        'file_path': 'src/css/main.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Main stylesheet for responsive layouts.'
                    },
                    {
                        'file_path': 'src/css/product-card.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Stylesheet for product card design.'
                    },
                    {
                        'file_path': 'src/js/main.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Main script implementing product filtering.'
                    },
                    {
                        'file_path': 'src/js/product-modal.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Script for displaying product details in a modal.'
                    }
                ]
            },
            'dialogue_context': {
                'text': '''请创建一个响应式的产品展示页面，包含以下功能：
            1. 主页面(index.html)：
               - 响应式网格布局展示产品
               - 产品过滤功能
            2. 样式文件：
               - 主样式(main.css)：响应式布局
               - 产品卡片样式(product-card.css)
            3. JavaScript文件：
               - 主逻辑(main.js)：实现产品过滤
               - 模态框(product-modal.js)：产品详情展示
            4. 依赖：
               - normalize.css用于样式重置
               - @popperjs/core用于模态框定位''',
                'type': 'CODE_RESOURCE',
                'tags': 'code_request,code_type_css,code_type_html,code_type_javascript,framework_normalize.css,framework_@popperjs/core'
            },
            'opera_id': str(OPERA_ID)
        },
        'source_dialogue_index': 1,
        'response_staff_id': STAFF_IDS['cm_staff_id'],
        'source_staff_id': STAFF_IDS['user_staff_id'],
        'progress': 0,
        'result': {'dialogue_id': 84, 'status': 'success'},
        'error_message': None,
        'retry_count': 0,
        'last_retry_at': None
    },
    {
        'id': UUID('433cab24-32be-4b60-a06f-8528564c2a15'),
        'created_at': TEST_TIME.replace(microsecond=268175),
        'started_at': TEST_TIME.replace(second=27, microsecond=720539),
        'completed_at': None,
        'priority': 3,  # TaskPriority.HIGH
        'type': 51,    # TaskType.RESOURCE_GENERATION
        'status': 3,   # TaskStatus.COMPLETED
        'description': '生成代码文件: src/html/index.html',
        'parameters': {
            'file_path': 'src/html/index.html',
            'file_type': 'html',
            'mime_type': 'text/html',
            'description': 'Main page file with responsive grid layout to display products.',
            'references': [
                'src/css/main.css',
                'src/css/product-card.css',
                'src/js/main.js',
                'src/js/product-modal.js'
            ],
            'code_details': {
                'project_type': 'web',
                'project_description': 'Responsive product showcase webpage with filtering functionality and modal product details display.',
                'requirements': [
                    'Responsive grid layout for product display',
                    'Product filtering functionality',
                    'Product details modal implementation'
                ],
                'frameworks': ['normalize.css', '@popperjs/core'],
                'resources': [
                    {
                        'file_path': 'src/html/index.html',
                        'type': 'html',
                        'mime_type': 'text/html',
                        'description': 'Main page file with responsive grid layout to display products.',
                        'references': [
                            'src/css/main.css',
                            'src/css/product-card.css',
                            'src/js/main.js',
                            'src/js/product-modal.js'
                        ]
                    },
                    {
                        'file_path': 'src/css/main.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Main stylesheet for responsive layouts.'
                    },
                    {
                        'file_path': 'src/css/product-card.css',
                        'type': 'css',
                        'mime_type': 'text/css',
                        'description': 'Stylesheet for product card design.'
                    },
                    {
                        'file_path': 'src/js/main.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Main script implementing product filtering.'
                    },
                    {
                        'file_path': 'src/js/product-modal.js',
                        'type': 'javascript',
                        'mime_type': 'text/javascript',
                        'description': 'Script for displaying product details in a modal.'
                    }
                ]
            },
            'dialogue_context': {
                'text': '''请创建一个响应式的产品展示页面，包含以下功能：
            1. 主页面(index.html)：
               - 响应式网格布局展示产品
               - 产品过滤功能
            2. 样式文件：
               - 主样式(main.css)：响应式布局
               - 产品卡片样式(product-card.css)
            3. JavaScript文件：
               - 主逻辑(main.js)：实现产品过滤
               - 模态框(product-modal.js)：产品详情展示
            4. 依赖：
               - normalize.css用于样式重置
               - @popperjs/core用于模态框定位''',
                'type': 'CODE_RESOURCE',
                'tags': 'code_request,code_type_css,code_type_html,code_type_javascript,framework_normalize.css,framework_@popperjs/core'
            },
            'opera_id': str(OPERA_ID)
        },
        'source_dialogue_index': 1,
        'response_staff_id': STAFF_IDS['cm_staff_id'],
        'source_staff_id': STAFF_IDS['user_staff_id'],
        'progress': 0,
        'result': {'dialogue_id': 86, 'status': 'success'},
        'error_message': None,
        'retry_count': 0,
        'last_retry_at': None
    }
]


def get_test_generation_tasks() -> list[BotTask]:
    """获取测试用的generation tasks
    
    将GENERATION_TASKS字典列表转换为BotTask对象列表
    
    Returns:
        list[BotTask]: BotTask对象列表
    """
    tasks = []
    for task_dict in GENERATION_TASKS:
        task = BotTask(
            id=task_dict['id'],
            created_at=task_dict['created_at'],
            started_at=task_dict.get('started_at'),
            completed_at=task_dict.get('completed_at'),
            priority=TaskPriority(task_dict['priority']),
            type=TaskType(task_dict['type']),
            status=TaskStatus(task_dict['status']),
            description=task_dict['description'],
            parameters=task_dict['parameters'],
            source_dialogue_index=task_dict.get('source_dialogue_index'),
            response_staff_id=task_dict.get('response_staff_id'),
            source_staff_id=task_dict.get('source_staff_id'),
            progress=task_dict.get('progress', 0),
            result=task_dict.get('result'),
            error_message=task_dict.get('error_message'),
            retry_count=task_dict.get('retry_count', 0),
            last_retry_at=task_dict.get('last_retry_at')
        )
        tasks.append(task)
    return tasks
