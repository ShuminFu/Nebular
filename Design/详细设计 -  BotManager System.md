## 1. SignalR Handler (消息监听层)

`SignalRHandler -(观察者)-> MessageProcessor -(责任链)-> BotMediator`
### 1.1 MessageObserver（观察者模式）

- IMessageObserver 接口
- SignalRMessageSubject
- ConcreteMessageObservers

## 2. Bot Factory (Bot创建工厂)

`IBotCapability -(接口)-> AbstractBotFactory -(工厂)-> BotInstancePool -(适配器)-> BotFrameworkAdapter`
### 2.1 AbstractBotFactory（抽象工厂模式）

#### 2.1.1 IBotFactory 接口

- createBot(capabilities: IBotCapability[])

- destroyBot(botId: string)

#### 2.1.2 BaseBotFactory

- 实现通用的Bot创建逻辑

- 管理Bot生命周期

#### 2.1.3 具体工厂实现

- AutogenBotFactory

- AiderBotFactory

- CrewAIBotFactory

### 2.2 BotFrameworkAdapter（适配器模式）

#### 2.2.1 IFrameworkAdapter 接口

- adaptCapabilities(capabilities: IBotCapability[])

- convertConfig(config: BotConfig)

#### 2.2.2 框架适配器实现

- AutogenAdapter

- AiderAdapter

- CrewAIAdapter

### 2.3 BotInstancePool（单例模式 + 对象池模式）

#### 2.3.1 BotPoolConfig #TBD

- 池化配置

- 扩缩容策略

### 2.4 Bot Capabilities（Bot能力接口）

#### 2.4.1 基础能力接口

- IRunnable（执行能力）

- IReadable（读取能力）

- IWritable（写入能力）

- IExecutable（命令执行能力）

### 2.5 BotCapabilityRegistry（能力注册中心）

#### 2.5.1 能力注册管理

- Function_call注册

- API_call注册

- 能力依赖管理

### 2.6 BotConfigurationCenter（配置中心）

#### 2.6.1 ConfigurationStore

- 存储原始配置

- 配置版本管理

- 配置持久化

#### 2.6.2 ConfigurationAdapter

##### 2.6.2.1 IConfigAdapter 接口

- adaptConfig(rawConfig) 方法

##### 2.6.2.2 具体适配器实现

- AutogenConfigAdapter

- AiderConfigAdapter

- CrewAIConfigAdapter

## 3. Bot Orchestrator (Bot编排层)
即时消息流传+持久化+同步
``` 
Bot A -> DirectMessageBus -> Bot B
     \-> SyncService (异步) -> Opera
```
### DirectMessageBus（消息总线）

#### IMessageBus 接口
- sendMessage(message: Message)
- broadcast(message: Message)
- subscribe(botId: string, handler: MessageHandler)

#### MessageQueue
- 优先级队列
- 消息去重
- 消息重试

### SyncService（同步服务）

#### BatchSyncProcessor
- 批量同步策略
- 失败重试机制
- 性能优化

#### ConflictResolver
- 冲突检测
- 冲突解决策略
- 数据一致性保证

### BotCoordinator（Bot协调器）

#### ResourceManager
- Bot资源分配
- 负载均衡
- 资源监控

#### TaskScheduler
- 任务优先级
- 任务分发
- 执行监控

## 4. Opera Integration (现有系统集成层)
数据流程
```
Opera System -(SignalR)-> SignalR Handler -(事件)-> BotManager
                                                      |
                                                      ↓
                                            需要操作时调用 OperaService
```
**BotManager调用Service层的业务方法**
- Service层组织业务逻辑，调用WebAPI
- WebAPI处理HTTP通信，使用Models进行数据交换
- Opera系统通过SignalR推送状态变更
  
依赖关系：
```
Services -> WebAPI -> Models
```
### Models（数据模型）
...
### WebAPI（接口定义）
#### IOperaAPI
##### Dialogue
##### Message
##### Stage
##### Bot
##### Resources
...
#### OperaAPIClient（实现）

### Services（业务服务）
#### IConversationService
- CreateConversation(CreateConversationRequest)
- GetConversation(string id)
- ...

#### IMessageService
- SendMessage(SendMessageRequest)
- ...

#### ConcreteServices（实现）
##### ConversationService
- 注入 IOperaAPI

##### MessageService
- 注入 IOperaAPI

[[Opera 集成模块的业务职责]]

## 5. State Management (状态管理) #TBD
### BotStateManager
### DialogueManager
### OperaStageManager
### RecoveryManager

# 备忘
```python
# 消息同步实现
class MessageSyncService:
    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.batch_size = 100
        self.sync_interval = 1  # seconds

    async def sync_messages(self):
        while True:
            batch = []
            try:
                while len(batch) < self.batch_size:
                    message = await self.message_queue.get()
                    batch.append(message)
            except asyncio.TimeoutError:
                if batch:
                    await self.opera_client.batch_sync(batch)
            await asyncio.sleep(self.sync_interval)
```

重构 见 [[详细设计V2]]

- 核心层(core/)处理基础抽象和管理

- 适配层(adapters/)处理不同框架的适配

- 集成层(integration/)处理与外部系统的交互