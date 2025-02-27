import pytest
from uuid import UUID
from src.core.topic.topic_tracker import TopicTracker
from src.core.task_utils import BotTask, TaskStatus, TaskType


@pytest.fixture
def topic_tracker():
    """创建TopicTracker实例"""
    return TopicTracker()


@pytest.fixture
def sample_task():
    """创建一个示例任务"""
    return BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="测试任务",
        topic_id="test-topic-1",
        topic_type="code_generation",
        parameters={"opera_id": "test-opera-1"},
    )


@pytest.fixture
def completion_callback_called():
    """用于追踪回调是否被调用的fixture"""
    called = {"count": 0, "args": None}

    async def callback(topic_id: str, opera_id: str):
        called["count"] += 1
        called["args"] = (topic_id, opera_id)

    return callback, called


@pytest.mark.asyncio
async def test_add_task(topic_tracker: TopicTracker, sample_task: BotTask):
    """测试添加任务到主题"""
    # 添加任务
    topic_tracker.add_task(sample_task)

    # 验证主题是否被创建
    topic_info = topic_tracker.get_topic_info("test-topic-1")
    assert topic_info is not None
    assert topic_info.type == "code_generation"
    assert topic_info.status == "active"
    assert topic_info.opera_id == "test-opera-1"
    assert sample_task.id in topic_info.tasks


@pytest.mark.asyncio
async def test_add_task_without_topic_id(topic_tracker: TopicTracker):
    """测试添加没有主题ID的任务"""
    task = BotTask(type=TaskType.RESOURCE_CREATION, description="无主题任务")

    # 添加任务
    topic_tracker.add_task(task)

    # 验证没有创建主题
    assert len(topic_tracker.topics) == 0


@pytest.mark.asyncio
async def test_update_task_status(topic_tracker: TopicTracker, sample_task: BotTask, completion_callback_called):
    """测试更新任务状态"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 添加任务
    topic_tracker.add_task(sample_task)

    # 更新状态为处理中
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.RUNNING, sample_task)
    assert called["count"] == 0  # 回调不应该被触发

    # 更新状态为完成
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED, sample_task)
    assert called["count"] == 1  # 回调应该被触发一次

    # 验证回调参数
    assert called["args"] == ("test-topic-1", "test-opera-1")

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-1")
    assert topic_info.status == "completed"


@pytest.mark.asyncio
async def test_multiple_tasks_completion(topic_tracker: TopicTracker, completion_callback_called):
    """测试多个任务的完成情况"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 创建两个任务
    task1 = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="任务1",
        topic_id="test-topic-2",
        topic_type="code_generation",
        parameters={"opera_id": "test-opera-2"},
    )

    task2 = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="任务2",
        topic_id="test-topic-2",
        topic_type="code_generation",
        parameters={"opera_id": "test-opera-2"},
    )

    # 添加任务
    topic_tracker.add_task(task1)
    topic_tracker.add_task(task2)

    # 完成第一个任务
    await topic_tracker.update_task_status(task1.id, TaskStatus.COMPLETED, task1)
    assert called["count"] == 0  # 回调不应该被触发

    # 完成第二个任务
    await topic_tracker.update_task_status(task2.id, TaskStatus.COMPLETED, task2)
    assert called["count"] == 1  # 回调应该被触发一次

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-2")
    assert topic_info.status == "completed"


@pytest.mark.asyncio
async def test_multiple_callbacks(topic_tracker: TopicTracker, sample_task: BotTask):
    """测试多个回调的情况"""
    callback_results = []

    async def callback1(topic_id: str, opera_id: str):
        callback_results.append(("callback1", topic_id))

    async def callback2(topic_id: str, opera_id: str):
        callback_results.append(("callback2", topic_id))

    # 注册多个回调
    topic_tracker.on_completion(callback1)
    topic_tracker.on_completion(callback2)

    # 添加并完成任务
    topic_tracker.add_task(sample_task)
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED, sample_task)

    # 验证所有回调都被触发
    assert len(callback_results) == 2
    assert ("callback1", "test-topic-1") in callback_results
    assert ("callback2", "test-topic-1") in callback_results


@pytest.mark.asyncio
async def test_update_nonexistent_task(topic_tracker: TopicTracker, completion_callback_called):
    """测试更新不存在的任务状态"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 更新一个不存在的任务
    await topic_tracker.update_task_status(UUID("00000000-0000-0000-0000-000000000000"), TaskStatus.COMPLETED, None)

    # 验证回调没有被触发
    assert called["count"] == 0


@pytest.mark.asyncio
async def test_completed_topic_no_duplicate_callback(
    topic_tracker: TopicTracker, sample_task: BotTask, completion_callback_called
):
    """测试已完成的主题不会重复触发回调"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 添加并完成任务
    topic_tracker.add_task(sample_task)
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED, sample_task)
    assert called["count"] == 1

    # 再次更新状态
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED, sample_task)
    assert called["count"] == 1  # 回调不应该被再次触发


@pytest.mark.asyncio
async def test_resource_path_update_after_completion(topic_tracker: TopicTracker):
    """测试资源创建任务完成后更新资源ID的功能"""
    # 创建一个资源创建任务，只有file_path，没有resource_id
    task = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="资源创建任务",
        topic_id="test-topic-3",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-3",
            "file_path": "src/main.py",
            # 注意：不包含 resource_id
        },
    )

    # 添加任务
    topic_tracker.add_task(task)

    # 验证文件路径已被记录到待处理列表
    assert task.id in topic_tracker._pending_resource_tasks
    assert topic_tracker._pending_resource_tasks[task.id] == "src/main.py"

    # 验证当前主题版本没有该文件的记录
    topic_info = topic_tracker.get_topic_info("test-topic-3")
    assert topic_info is not None
    if topic_info.current_version:
        file_entries = [entry for entry in topic_info.current_version.current_files if entry["file_path"] == "src/main.py"]
        assert len(file_entries) == 0

    # 模拟任务完成，并设置结果中包含resource_id
    task.result = {"resource_id": "res-123", "status": "success"}
    await topic_tracker.update_task_status(task.id, TaskStatus.COMPLETED, task)

    # 验证文件路径已从待处理列表中移除
    assert task.id not in topic_tracker._pending_resource_tasks

    # 验证文件映射已更新
    topic_info = topic_tracker.get_topic_info("test-topic-3")
    assert topic_info is not None
    assert topic_info.current_version is not None

    # 验证在 current_files 和 modified_files 中都有正确的记录
    for files_list in [topic_info.current_version.current_files, topic_info.current_version.modified_files]:
        file_entries = [entry for entry in files_list if entry["file_path"] == "src/main.py"]
        assert len(file_entries) == 1
        assert file_entries[0]["resource_id"] == "res-123"


@pytest.mark.asyncio
async def test_multiple_resources_path_update(topic_tracker: TopicTracker):
    """测试多个资源创建任务的文件路径更新"""
    # 创建多个资源创建任务
    task1 = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="资源创建任务1",
        topic_id="test-topic-4",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-4",
            "file_path": "src/index.html",
        },
    )

    task2 = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="资源创建任务2",
        topic_id="test-topic-4",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-4",
            "file_path": "src/style.css",
        },
    )

    # 添加任务
    topic_tracker.add_task(task1)
    topic_tracker.add_task(task2)

    # 验证文件路径已被记录到待处理列表
    assert task1.id in topic_tracker._pending_resource_tasks
    assert task2.id in topic_tracker._pending_resource_tasks
    assert topic_tracker._pending_resource_tasks[task1.id] == "src/index.html"
    assert topic_tracker._pending_resource_tasks[task2.id] == "src/style.css"

    # 模拟任务1完成，并设置结果中包含resource_id
    task1.result = {"resource_id": "res-html", "status": "success"}
    await topic_tracker.update_task_status(task1.id, TaskStatus.COMPLETED, task1)

    # 验证任务1的文件路径已从待处理列表中移除，但任务2仍在
    assert task1.id not in topic_tracker._pending_resource_tasks
    assert task2.id in topic_tracker._pending_resource_tasks

    # 验证任务1的文件映射已更新
    topic_info = topic_tracker.get_topic_info("test-topic-4")
    file_entries = [entry for entry in topic_info.current_version.current_files if entry["file_path"] == "src/index.html"]
    assert len(file_entries) == 1
    assert file_entries[0]["resource_id"] == "res-html"

    # 模拟任务2完成，并设置结果中包含resource_id
    task2.result = {"resource_id": "res-css", "status": "success"}
    await topic_tracker.update_task_status(task2.id, TaskStatus.COMPLETED, task2)

    # 验证任务2的文件路径也已从待处理列表中移除
    assert task2.id not in topic_tracker._pending_resource_tasks

    # 验证任务2的文件映射已更新
    topic_info = topic_tracker.get_topic_info("test-topic-4")
    file_entries = [entry for entry in topic_info.current_version.current_files if entry["file_path"] == "src/style.css"]
    assert len(file_entries) == 1
    assert file_entries[0]["resource_id"] == "res-css"

    # 验证所有文件都在列表中
    assert len(topic_info.current_version.current_files) == 2
    assert len(topic_info.current_version.modified_files) == 2


@pytest.mark.asyncio
async def test_update_task_without_result(topic_tracker: TopicTracker):
    """测试没有结果的任务状态更新"""
    # 创建一个资源创建任务
    task = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="资源创建任务",
        topic_id="test-topic-5",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-5",
            "file_path": "src/app.js",
        },
    )

    # 添加任务
    topic_tracker.add_task(task)

    # 验证文件路径已被记录到待处理列表
    assert task.id in topic_tracker._pending_resource_tasks

    # 模拟任务完成，但不设置结果
    await topic_tracker.update_task_status(task.id, TaskStatus.COMPLETED, task)

    # 验证文件路径仍在待处理列表中（因为没有resource_id）
    assert task.id in topic_tracker._pending_resource_tasks

    # 验证文件映射未更新
    topic_info = topic_tracker.get_topic_info("test-topic-5")
    if topic_info.current_version:
        file_entries = [entry for entry in topic_info.current_version.current_files if entry["file_path"] == "src/app.js"]
        assert len(file_entries) == 0


@pytest.mark.asyncio
async def test_task_counter_update(topic_tracker: TopicTracker):
    """测试任务计数器的更新"""
    # 创建一个RESOURCE_GENERATION任务
    gen_task = BotTask(
        type=TaskType.RESOURCE_GENERATION,
        description="生成任务",
        topic_id="test-topic-counter",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-counter",
            "expected_files_count": 3,  # 预期生成3个文件
        },
    )

    # 添加生成任务
    topic_tracker.add_task(gen_task)

    # 验证预期创建任务数量
    topic_info = topic_tracker.get_topic_info("test-topic-counter")
    assert topic_info.expected_creation_count == 3
    assert topic_info.actual_creation_count == 0
    assert topic_info.completed_creation_count == 0

    # 创建一个RESOURCE_CREATION任务
    create_task = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="创建任务1",
        topic_id="test-topic-counter",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-counter",
            "file_path": "src/file1.py",
        },
    )

    # 添加创建任务
    topic_tracker.add_task(create_task)

    # 验证实际创建任务数量
    topic_info = topic_tracker.get_topic_info("test-topic-counter")
    assert topic_info.expected_creation_count == 3
    assert topic_info.actual_creation_count == 1
    assert topic_info.completed_creation_count == 0

    # 模拟创建任务完成
    create_task.result = {"resource_id": "res-file1", "status": "success"}
    await topic_tracker.update_task_status(create_task.id, TaskStatus.COMPLETED, create_task)

    # 验证已完成创建任务数量
    topic_info = topic_tracker.get_topic_info("test-topic-counter")
    assert topic_info.completed_creation_count == 1
    assert topic_info.status == "active"  # 还没有达到预期数量，所以状态保持active


@pytest.mark.asyncio
async def test_topic_completion_based_on_expected_count(topic_tracker: TopicTracker, completion_callback_called):
    """测试基于预期数量的主题完成逻辑"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 创建一个RESOURCE_GENERATION任务
    gen_task = BotTask(
        type=TaskType.RESOURCE_GENERATION,
        description="生成任务",
        topic_id="test-topic-expected",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-expected",
            "expected_files_count": 2,  # 预期生成2个文件
        },
    )

    # 添加生成任务
    topic_tracker.add_task(gen_task)

    # 创建2个RESOURCE_CREATION任务
    create_tasks = []
    for i in range(2):
        task = BotTask(
            type=TaskType.RESOURCE_CREATION,
            description=f"创建任务{i + 1}",
            topic_id="test-topic-expected",
            topic_type="code_generation",
            parameters={
                "opera_id": "test-opera-expected",
                "file_path": f"src/file{i + 1}.py",
            },
        )
        create_tasks.append(task)
        topic_tracker.add_task(task)

    # 完成第一个创建任务
    create_tasks[0].result = {"resource_id": "res-file1", "status": "success"}
    await topic_tracker.update_task_status(create_tasks[0].id, TaskStatus.COMPLETED, create_tasks[0])
    assert called["count"] == 0  # 回调不应该被触发，因为只完成了一个任务

    # 完成第二个创建任务
    create_tasks[1].result = {"resource_id": "res-file2", "status": "success"}
    await topic_tracker.update_task_status(create_tasks[1].id, TaskStatus.COMPLETED, create_tasks[1])
    assert called["count"] == 1  # 回调应该被触发，因为已完成的创建任务数量达到预期

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-expected")
    assert topic_info.status == "completed"

    # 即使生成任务还未完成，主题也应该被标记为完成
    assert gen_task.id not in topic_tracker._completed_tasks["test-topic-expected"]


@pytest.mark.asyncio
async def test_topic_completion_based_on_actual_count(topic_tracker: TopicTracker, completion_callback_called):
    """测试基于实际创建任务数量的主题完成逻辑"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 创建主题，但不设置预期数量
    # 直接创建3个RESOURCE_CREATION任务
    create_tasks = []
    for i in range(3):
        task = BotTask(
            type=TaskType.RESOURCE_CREATION,
            description=f"创建任务{i + 1}",
            topic_id="test-topic-actual",
            topic_type="code_generation",
            parameters={
                "opera_id": "test-opera-actual",
                "file_path": f"src/file{i + 1}.py",
            },
        )
        create_tasks.append(task)
        topic_tracker.add_task(task)

    # 验证计数
    topic_info = topic_tracker.get_topic_info("test-topic-actual")
    assert topic_info.expected_creation_count == 0  # 没有设置预期数量
    assert topic_info.actual_creation_count == 3  # 有3个实际创建任务

    # 完成两个创建任务
    for i in range(2):
        create_tasks[i].result = {"resource_id": f"res-file{i + 1}", "status": "success"}
        await topic_tracker.update_task_status(create_tasks[i].id, TaskStatus.COMPLETED, create_tasks[i])

    assert called["count"] == 0  # 回调不应该被触发，因为还有一个任务未完成

    # 完成最后一个创建任务
    create_tasks[2].result = {"resource_id": "res-file3", "status": "success"}
    await topic_tracker.update_task_status(create_tasks[2].id, TaskStatus.COMPLETED, create_tasks[2])
    assert called["count"] == 1  # 回调应该被触发，因为所有创建任务都已完成

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-actual")
    assert topic_info.status == "completed"


@pytest.mark.asyncio
async def test_generation_task_completion_no_check(topic_tracker: TopicTracker, completion_callback_called):
    """测试RESOURCE_GENERATION任务完成不会触发主题完成检查"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 创建一个RESOURCE_GENERATION任务
    gen_task = BotTask(
        type=TaskType.RESOURCE_GENERATION,
        description="生成任务",
        topic_id="test-topic-gen",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-gen",
            "expected_files_count": 1,
        },
    )

    # 添加生成任务
    topic_tracker.add_task(gen_task)

    # 模拟生成任务完成
    await topic_tracker.update_task_status(gen_task.id, TaskStatus.COMPLETED, gen_task)
    assert called["count"] == 0  # 回调不应该被触发，即使任务完成

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-gen")
    assert topic_info.status == "active"  # 主题应该仍然是活动状态

    # 创建一个RESOURCE_CREATION任务
    create_task = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="创建任务",
        topic_id="test-topic-gen",
        topic_type="code_generation",
        parameters={
            "opera_id": "test-opera-gen",
            "file_path": "src/file.py",
        },
    )

    # 添加并完成创建任务
    topic_tracker.add_task(create_task)
    create_task.result = {"resource_id": "res-file", "status": "success"}
    await topic_tracker.update_task_status(create_task.id, TaskStatus.COMPLETED, create_task)

    assert called["count"] == 1  # 现在回调应该被触发

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-gen")
    assert topic_info.status == "completed"  # 主题现在应该完成
