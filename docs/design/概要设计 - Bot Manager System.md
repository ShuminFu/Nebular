# Resources
#### 智能盘点的参考点
通过Process 来部署一个模型进程，并且在数据库中记录跟这个模型相关的信息（部署状态， 模型信息），并基此支持系统重启后的自动重新部署。
然后主程序通过HTTP 请求来跟进程通信。

# 概要设计

BotManager System (修改建议)
├── [[SignalR Handler]] (消息监听层)
│   ├── MessageObserver
│   └── StateChangeNotifier
├── [[Bot Factory]] (Bot创建工厂)
│   ├── BotFrameworkAdapter
│   └── BotInstancePool
├── [[Bot Orchestrator]] (Bot编排层)
│   ├── MessageRouter
│   ├── ConversationManager
│   └── BotMediator
└── [[Opera Integration]] (现有系统集成层)
    ├── OperaAdapter
    └── SyncManager

# 详细设计
#### [[详细设计 -  BotManager System]]


#### 数据流
SignalR消息 -> SignalR Handler -> Bot Orchestrator -> Bot Factory
                                                   -> Opera System
                                                   -> Bot Communication



# 备忘
##### 适配器
转换LLM的KEY，BASE_URL等
##### 状态管理
```python
# 检查所有Bot状态

for bot_id, bot in self.bots.items():

if not await bot.is_healthy():

logger.warning(f"Bot {bot_id} unhealthy, recreating...")

await self.recreate_bot(bot_id)
```
##### 扩展
- 支持新增Bot框架
- 支持新的通信协议
- 支持自定义Bot行为

- ==容错性==
- SignalR断线重连
- Bot异常恢复
- 消息重试机制

- ==性能优化==
- Bot池化管理
- 消息队列
- 异步处理

- ==监控告警==
- Bot健康检查
- 性能指标收集
- 异常监控