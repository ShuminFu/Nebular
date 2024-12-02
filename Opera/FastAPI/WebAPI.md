Bot管理：http://opera.nti56.com/Bot

功能：获取所有Bot。
方法：Get
地址：/
返回值：List<Bot>，其中Bot包含属性：Guid Id，string Name，string? Description，bool IsActive，string? CallShellOnOperaStarted，string? DefaultTag，string? DefaultRoles，string? DefaultPermissions。

功能：返回指定Bot。
方法：Get
地址：/{botId}
返回值：Bot，属性同上；当找不到时，返回404。

功能：创建Bot。
方法：Post
地址：/
Body参数：BotForCreation bot，其中bot包含属性：string Name，string? Description，string? CallShellOnOperaStarted，string? DefaultTags，string? DefaultRoles，string? DefaultPermissions。
返回值：创建的Bot，属性同上；失败返回错误信息。

功能：更新Bot信息。
方法：Put
地址：/{botId}
Body参数：BotForUpdate bot，其中bot包含属性：string? Name（为null时不更新名称），bool IsDescriptionUpdated，string? Description，bool IsCallShellOnOperaStartedUpdated，string? CallShellOnOperaStarted，bool IsDefaultTagsUpdated，string? DefaultTags，bool IsDefaultRolesUpdated，string? DefaultRoles，bool IsDefaultPermissionsUpdated，string? DefaultPermissions。其中bool为false时，其后一个值会被忽略。
返回值：成功返回204；失败返回错误信息。

功能：删除Bot。
方法：Delete
地址：/{botId}
返回值：成功返回204；失败返回错误信息。

--------

Opera管理：http://opera.nti56.com/Opera

功能：获取所有Opera。
方法：Get
地址：/
参数：Guid? parentId，父Opera。当不指定时，返回以根为父节点的Opera。
返回值：List<OperaWithMaintenanceState>，其中OperaWithMaintenanceState包含属性：Guid Id，Guid? ParentId，string Name，string? Description，string DatabaseName，int MaintenanceState。MaintenanceState为0表示状态正常；MaintenanceState为1表示正在创建；MaintenanceState为2表示正在删除。

功能：获取指定Opera。
方法：Get
地址：/{operaId}
返回值：OperaWithMaintenanceState，属性同上；当找不到时，返回404。

功能：创建Opera。
方法：Post
地址：/
Body参数：OperaForCreation opera，其中opera包含属性：Guid? ParentId，string Name，string? Description，string DatabaseName。
返回值：创建的Opera，包含属性：Guid Id，Guid? ParentId，string Name，string? Description，string DatabaseName；失败返回错误信息。

功能：更新Opera信息。
方法：Put
地址：/{operaId}
Body参数：OperaForUpdate opera，其中opera包含属性：string? Name（为null时不更新名称），bool IsDescriptionUpdated，string? Description。其中bool为false时，其后一个值会被忽略。
返回值：成功返回204；失败返回错误信息。

功能：删除Opera。
方法：Delete
地址：/{operaId}
返回值：成功返回204；失败返回错误信息。

--------

属性管理：http://opera.nti56.com/Opera/{operaId}/Property

功能：获取所有属性。
方法：Get
地址：/
参数：bool? force：当指定且为true时，强制穿透缓存，从数据库读取。
返回值：OperaProperty，其中包含字典Properties；当指定的Opera不存在时，返回404。

功能：获取指定的属性。
方法：Get
地址：/ByKey
参数：string key：指定的属性名；bool? force：当指定且为true时，强制穿透缓存，从数据库读取。
返回值：成功返回200以及属性值；当属性找不到时，返回204；当指定的Opera不存在时，返回404。

功能：更新属性。
方法：Put
地址：/
Body参数：OperaPropertyForUpdate property，其中property可选包含字典Properties，当存在时，将使用字典的元素替代现有的属性或新增对应的属性；property可选包含集合PropertiesToRemove，当存在时，以这些元素为属性名的属性会被删除。
返回值：成功返回204；失败返回错误信息；当指定的Opera不存在时，返回404。

--------

职员管理：http://opera.nti56.com/Opera/{operaId}/Staff

功能：获取所有职员。
方法：Get
地址：/
返回值：List<Staff>，其中Staff包含属性：Guid Id，Guid BotId，string Name，string Parameter，bool IsOnStage，string Tags，string Roles，string Permissions。

功能：获取所有职员。
方法：Post
地址：/Get
Body参数：StaffForFilter? filter，其中filter包含属性：Guid? BotId，string? Name，string? NameLike，bool? IsOnStage。
返回值：List<Staff>，其中Staff属性同上。

功能：获取指定Name的职员。
方法：Get
地址：/ByName
参数：string name，职员Name；bool? isOnStage，当指定且为true时，只处理OnStage的职员。
返回值：List<Staff>，其中Staff属性同上。

功能：获取指定Name的职员。
方法：Get
地址：/ByNameLike
参数：string nameLike，职员Name以Like方式匹配；bool? isOnStage，当指定且为true时，只处理OnStage的职员。
返回值：List<Staff>，其中Staff属性同上。

功能：获取指定职员。
方法：Get
地址：/{staffId}
返回值：Staff，属性同上；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：创建职员。
方法：Post
地址：/
Body参数：StaffForCreation staff，其中staff包含属性：Guid BotId，string Name，string Parameter，bool IsOnStage，string Tags，string Roles，string Permission。
返回值：Staff，属性同上；失败返回错误信息；当指定的Opera不存在时，返回404。

功能：更新职员信息。
方法：Get
地址：/{staffId}/Update
参数：bool? isOnStage，非空则更新OnStage；string? parameter，非空则更新Parameter。
返回值：成功返回204；无需修改返回304；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：更新职员信息。
方法：Put
地址：/{staffId}
Body参数：StaffForUpdate staff，其中staff包含属性：bool? IsOnStage，string? Parameter。按需更新。
返回值：成功返回204；无需修改返回304；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：删除职员。
方法：Delete
地址：/{staffId}
返回值：成功返回204；失败返回错误信息；当找不到时，返回404；当指定的Opera不存在时，返回404。

--------

职员邀请管理：http://opera.nti56.com/Opera/{operaId}/StaffInvitation

功能：获取所有职员邀请。
方法：Get
地址：/
返回值：List<StaffInvitation>，其中StaffInvitation包含属性：Guid Id，Guid BotId，string Parameter，string Tags，string Roles，string Permissions。

功能：获取指定职员邀请。
方法：Get
地址：/{staffInvitationId}
返回值：StaffInvitation，属性同上；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：创建职员邀请。
方法：Post
地址：/
Body参数：StaffInvitationForCreation staffInvitation，其中staffInvitation包含属性：Guid BotId，string Parameter，string Tags，string Roles，string Permission。
返回值：StaffInvitation，属性同上；失败返回错误信息；当指定的Opera不存在时，返回404。

功能：删除职员邀请。
方法：Delete
地址：/{staffInvitationId}
返回值：成功返回204；失败返回错误信息；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：接受职员邀请。
方法：Post
地址：/{staffInvitationId}/Accpet
Body参数：StaffInvitationForAcceptance staffInvitation，其中staffInvitation包含属性：string Name，string? Parameter，bool IsOnStage，string? Tags，string? Roles，string? Permission。可选属性如未指定则使用邀请中的值。
返回值：成功返回创建的职员Id；失败返回错误信息；当找不到时，返回404；当指定的Opera不存在时，返回404。
注：此功能的ETag为职员Id，而非职员邀请Id。

--------

场幕管理：http://opera.nti56.com/Opera/{operaId}/Stage

功能：获取所有场幕。
方法：Get
地址：/
返回值：List<Stage>，其中Stage包含属性：int Index，string Name；当指定的Opera不存在时，返回404。

功能：获取当前场幕。
方法：Get
地址：/Current 或 /-1
属性：bool? force，当指定且为true时，强制穿透缓存，从数据库读取。
返回值：Stage，属性同上；当找不到时，返回204；当指定的Opera不存在时，返回404。

功能：获取指定场幕。
方法：Get
地址：/{stageIndex}
返回值：Stage，属性同上；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：创建场幕。
方法：Post
地址：/
Body参数：StageForCreation stage，其中stage包含属性：string Name。
返回值：创建的Stage，属性同上；失败返回错误信息；当指定的Opera不存在时，返回404。

--------

临时文件管理：http://opera.nti56.com/TempFile

功能：上传临时文件。
方法：Post
地址：/
参数：Guid? id，临时文件Id。当指定时，附加数据到指定的临时文件；当不指定时，创建新的临时文件。
Body参数：文件数据块（chunk）。
返回值：TempFile，包含属性：Guid Id，临时文件Id；long Length，到目前为止的此临时文件总长度。失败返回错误信息。如果指定的临时文件不存在，返回404。

功能：附加临时文件。同上传临时文件并指定临时文件Id。
方法：Post
地址：/{id}
Body参数：文件数据块（chunk）。
返回值：TempFile，包含属性：Guid Id，临时文件Id；long Length，到目前为止的此临时文件总长度。失败返回错误信息。如果指定的临时文件不存在，返回404。

功能：删除临时文件。
方法：Delete
地址：/{id}
返回值：成功返回204；如果指定的临时文件不存在，返回404。

注：临时文件目录在每次Opera启动时将被清空。当临时文件被作为资源文件使用时，会被移出临时文件目录。

--------

资源文件管理：http://opera.nti56.com/Opera/{operaId}/Resource

功能：获取所有资源文件。
方法：Get
地址：/
返回值：List<Resource>，其中Resource包含属性：Guid Id，string Name，string Description，string MimeType，DateTime LastUpdateTime，string LastUpdateStaffName；当指定的Opera不存在时，返回404。

功能：获取所有资源文件。
方法：Post
地址：/Get
Body参数：ResourceForFilter? filter，其中filter包含属性：string? Name，string? NameLike，string? MimeType，string? MimeTypeLike，DateTime? LastUpdateTimeNotBefore，DateTime? LastUpdateTimeNotAfter，string? LastUpdateStaffName，string? LastUpdateStaffNameLike。
返回值：List<Resource>，其中Resource属性同上；当指定的Opera不存在时，返回404。

功能：获取指定资源文件。
方法：Get
地址：/{resourceId}
返回值：Resource，属性同上；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：下载资源文件。
方法：Get
地址：/{resourceId}/Download 或 /Download/{resourceId}
返回值：文件流；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：创建资源文件。创建资源文件前，应先将文件上传为临时文件。
方法：Post
地址：/
Body参数：ResourceForCreation resource，其中resource包含属性：string Name，string Description，string MimeType，string LastUpdateStaffName，Guid TempFileId。
返回值：创建的Resource，属性同上；失败返回错误信息；当指定的Opera不存在时，返回404。

功能：更新资源文件。如需更新资源文件，应先将文件上传为临时文件。
方法：Put
地址：/{resourceId}
Body参数：ResourceForUpdate resource，其中resource包含属性：string? Name，string? Description，string? MimeType，string LastUpdateStaffName，Guid? TempFileId。可选属性如未指定则不会修改。
返回值：成功返回204；失败返回错误信息；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：删除资源文件。
方法：Delete
地址：/{resourceId}
返回值：成功返回204；失败返回错误信息；当找不到时，返回404；当指定的Opera不存在时，返回404。

--------

对话管理：http://opera.nti56.com/Opera/{operaId}/Dialogue

功能：获取所有对话。
方法：Get
地址：/
返回值：List<Dialogue>，其中Dialogue包含属性：int Index，DateTime Time，int? StageIndex，Guid? StaffId，bool IsNarratage，bool IsWhisper，string Text，sring? Tags，List<Guid>? MentionedStaffIds；当指定的Opera不存在时，返回404。

功能：获取所有对话。
方法：Post
地址：/Get
Body参数：DialogueForFilter? filter，其中filter包含属性：int? IndexNotBefore，int? IndexNotAfter，int? TopLimit，int? StageIndex，bool IncludesStageIndexNull，bool IncludesNarratage，Guid? IncludesForStaffIdOnly，bool IncludesStaffIdNull。其中TopLimit默认值100；如需获取所有职员的信息，不要设置IncludesForStaffIdOnly。
返回值：List<Dialogue>，其中Dialogue属性同上；当指定的Opera不存在时，返回404。

功能：获取指定对话。
方法：Get
地址：/{dialogueIndex}
返回值：Dialogue，属性同上；当找不到时，返回404；当指定的Opera不存在时，返回404。

功能：创建对话。
方法：Post
地址：/
Body参数：DialogueForCreation dialogue，其中dialogue包含属性：bool IsStageIndexNull，Guid? StaffId，bool IsNarratage，bool IsWhisper，string Text，string? Tags，List<Guid>? MentionedStaffIds。
返回值：创建的Dialogue，属性同上；失败返回错误信息；当指定的Opera不存在时，返回404。

--------

备注：
1 方法指Http方法，地址为相对地址。当地址为/时可忽略此地址。
2 类型以?结尾的表示可以为空。
3 Bot的IsActive为只读，表明此Bot目前存在到Opera的SignalR连接。
4 来自Body的参数，除有特别声明，使用Json封装。类型以?为结尾的属性可以忽略。
5 Filter参数存在时，用于在查询时过滤结果。其中有值的属性会被使用。Like结尾的属性使用数据库的Like %...%方式过滤数据。同时指定属性与Like结尾的属性时，Like结尾的属性会被忽略。