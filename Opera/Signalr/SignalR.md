地址：http://opera.nti56.com/signalRService

连接成功后，应立即调用SetBotId(Guid botId)方法，将当前Bot的Id传入，以便服务器识别当前Bot。SetBotId调用成功后，服务器会立即回调Hello方法；如传入botId为空或与已设置的botId相同，则不会回调Hello方法。

可以调用SetSnitchMode(bool snitchMode)方法，设置是否开启告密模式。告密模式开启后，Opera会将所有对话转发至此链接；默认情况下，只会转发与此Bot相关的数据。

在使用期间，如连接中断，应主动恢复连接，并在连接后重新调用SetBotId方法，以及按需调用SetSnitchMode方法。

本地应注册下列方法：

方法：Hello
调用：当SetBotId被调用，botId非空且与已存储的值不同时，此方法会被调用。

方法：OnSystemShutdown
调用：当Opera系统即将关闭时，此方法会被调用。

方法：OnOperaCreated(args)
   args: structure
       operaId: guid,
       parentId: guid (nullable),
       name: string,
       description: string (nullable),
       databaseName: string
调用：当Opera被创建时，此方法会被调用。

方法：OnOperaDeleted(args)
   args: structure
       operaId: guid
调用：当Opera被删除时，此方法会被调用。

方法：OnStaffInvited(args)
   args: structure
       operaId: guid,
       invitationId: guid,
       parameter: string (json),
       tags: string,
       roles: string,
       permissions: string
调用：当此Bot被邀请作为职员时，此方法会被调用。

方法：OnStageChanged(args)
   args: structure
       operaId: guid,
       stageIndex: number,
       stageName: string
调用：当Opera的场幕发生变化时，此方法会被调用。

方法：OnMessageReceived(args)
   args: structure
       OperaId: guid,
       ReceiverStaffIds[]: guid[],
       Index: number,
       Time: string (datetime),
       StageIndex: number (nullable, has value when sender choose to apply on a stage),
       SenderStaffId: guid (nullable, has value when sender reveal his/her identity),
       IsNarratage: boolean,
       IsWhisper: boolean,
       Text: string,
       Tags: string (nullable),
       MentionedStaffIds: guid[] (nullable, always has value when isWhisper is true, has value when mentioned some staffs)
调用：当有消息需要被此Bot处理时，此方法会被调用。