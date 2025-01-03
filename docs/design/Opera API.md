## 1. 系统概述

Opera是一个复杂的多角色交互和场景管理平台，支持多层级结构和灵活的交互管理。

## 2. 系统架构

### 2.1 层级结构

- Opera层级：支持父子Opera嵌套
- 职员层级：通过Bot关联
- 场景层级：有序的场景管理
- 权限层级：细粒度的角色和权限控制

## 3. 核心功能模块

### 3.1 Opera管理

- 创建、查询、更新和删除Opera
- 支持多层级Opera关系
- 管理Opera基本属性和状态

### 3.2 职员(Staff)管理

- 创建和管理不同Bot下的职员
- 职员属性：
    - 标签
    - 角色
    - 权限
- 职员邀请和接受机制

### 3.3 场景(Stage)管理

- 创建和管理场景
- 追踪当前场景
- 场景索引和命名

### 3.4 对话(Dialogue)系统

- 对话记录和管理
- 对话类型：
    - 普通对话
    - 旁白
    - 悄悄话
- 职员和场景关联
- 提及其他职员功能

### 3.5 资源(Resource)管理

- 文件资源上传
- 支持多种MIME类型
- 资源更新追踪
- 资源元数据管理

### 3.6 临时文件(TempFile)处理

- 文件上传机制
- 临时文件管理
- 文件分块上传支持

### 3.7 属性(Property)管理

- 灵活的键值对属性设置
- 动态属性更新
- 属性继承和覆盖

## 4. 系统组件关联模型

### 1.1 Bot (机器人/角色生成器)

- 唯一标识：UUID
- 核心属性：
    - 名称
    - 描述
    - 是否激活
    - 默认标签
    - 默认角色
    - 默认权限
- 功能：作为Staff的模板和生成源

### 1.2 Staff (角色/职员)

- 与Bot的关系：
    - 每个Staff必须关联一个Bot
    - 继承Bot的默认属性
- 唯一标识：UUID
- 核心属性：
    - 名称
    - 关联的BotID
    - 是否在舞台上
    - 个性化参数
    - 标签
    - 角色
    - 权限

### 1.3 Opera (剧场/项目)

- 唯一标识：UUID
- 层级关系：
    - 可以有父Opera
    - 可以创建子Opera
- 核心属性：
    - 名称
    - 描述
    - 数据库名称
    - 维护状态

## 2. 组件交互流程

### 2.1 Bot创建流程

1. 创建Bot模板
2. 设置默认属性
3. 可用于生成Staff

### 2.2 Staff生成流程

1. 选择Bot模板
2. 继承Bot默认属性
3. 个性化配置
4. 可邀请加入Opera

### 2.3 Opera管理流程

1. 创建Opera
2. 可设置父Opera
3. 邀请Staff加入
4. 管理场景和对话

### 2.4 关联机制示例
```python
# Bot创建
bot = {
    "id": "bot-uuid-1",
    "name": "默认角色生成器",
    "default_tags": "智能,可交互",
    "default_roles": "助手",
    "default_permissions": "read,write"
}

# Staff生成
staff = {
    "id": "staff-uuid-1", 
    "bot_id": "bot-uuid-1",  # 关联Bot
    "name": "小助手",
    "is_on_stage": True,
    "tags": "智能,可交互",  # 继承自Bot
    "roles": "助手",        # 继承自Bot
    "parameter": "{...}"   # 个性化配置
}

# Opera管理
opera = {
    "id": "opera-uuid-1",
    "name": "测试剧场",
    "parent_id": "opera-parent-uuid",  # 可选的父Opera
    "staff_list": ["staff-uuid-1", "staff-uuid-2"]
}

```

### 2.5 关键关联特点

- Bot是Staff的模板和生成源
- Staff可以加入不同的Opera
- Opera可以有多个Staff
- 属性可以层级继承和覆盖