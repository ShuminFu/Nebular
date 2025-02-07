import pytest
from uuid import UUID, uuid4
from src.core.topic.topic_tracker import TopicTracker, TopicInfo
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
        parameters={"opera_id": "test-opera-1"}
    )


@pytest.fixture
def completion_callback_called():
    """用于追踪回调是否被调用的fixture"""
    called = {"count": 0, "args": None}

    async def callback(topic_id: str, topic_type: str, opera_id: str):
        called["count"] += 1
        called["args"] = (topic_id, topic_type, opera_id)

    return callback, called


@pytest.mark.asyncio
async def test_add_task(topic_tracker, sample_task):
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
async def test_add_task_without_topic_id(topic_tracker):
    """测试添加没有主题ID的任务"""
    task = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="无主题任务"
    )

    # 添加任务
    topic_tracker.add_task(task)

    # 验证没有创建主题
    assert len(topic_tracker.topics) == 0


@pytest.mark.asyncio
async def test_update_task_status(topic_tracker, sample_task, completion_callback_called):
    """测试更新任务状态"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 添加任务
    topic_tracker.add_task(sample_task)

    # 更新状态为处理中
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.RUNNING)
    assert called["count"] == 0  # 回调不应该被触发

    # 更新状态为完成
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED)
    assert called["count"] == 1  # 回调应该被触发一次

    # 验证回调参数
    assert called["args"] == ("test-topic-1", "code_generation", "test-opera-1")

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-1")
    assert topic_info.status == "completed"


@pytest.mark.asyncio
async def test_multiple_tasks_completion(topic_tracker, completion_callback_called):
    """测试多个任务的完成情况"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 创建两个任务
    task1 = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="任务1",
        topic_id="test-topic-2",
        topic_type="code_generation",
        parameters={"opera_id": "test-opera-2"}
    )

    task2 = BotTask(
        type=TaskType.RESOURCE_CREATION,
        description="任务2",
        topic_id="test-topic-2",
        topic_type="code_generation",
        parameters={"opera_id": "test-opera-2"}
    )

    # 添加任务
    topic_tracker.add_task(task1)
    topic_tracker.add_task(task2)

    # 完成第一个任务
    await topic_tracker.update_task_status(task1.id, TaskStatus.COMPLETED)
    assert called["count"] == 0  # 回调不应该被触发

    # 完成第二个任务
    await topic_tracker.update_task_status(task2.id, TaskStatus.COMPLETED)
    assert called["count"] == 1  # 回调应该被触发一次

    # 验证主题状态
    topic_info = topic_tracker.get_topic_info("test-topic-2")
    assert topic_info.status == "completed"


@pytest.mark.asyncio
async def test_multiple_callbacks(topic_tracker, sample_task):
    """测试多个回调的情况"""
    callback_results = []

    async def callback1(topic_id: str, topic_type: str, opera_id: str):
        callback_results.append(("callback1", topic_id))

    async def callback2(topic_id: str, topic_type: str, opera_id: str):
        callback_results.append(("callback2", topic_id))

    # 注册多个回调
    topic_tracker.on_completion(callback1)
    topic_tracker.on_completion(callback2)

    # 添加并完成任务
    topic_tracker.add_task(sample_task)
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED)

    # 验证所有回调都被触发
    assert len(callback_results) == 2
    assert ("callback1", "test-topic-1") in callback_results
    assert ("callback2", "test-topic-1") in callback_results


@pytest.mark.asyncio
async def test_update_nonexistent_task(topic_tracker, completion_callback_called):
    """测试更新不存在的任务状态"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 更新一个不存在的任务
    await topic_tracker.update_task_status(UUID('00000000-0000-0000-0000-000000000000'), TaskStatus.COMPLETED)

    # 验证回调没有被触发
    assert called["count"] == 0


@pytest.mark.asyncio
async def test_completed_topic_no_duplicate_callback(topic_tracker, sample_task, completion_callback_called):
    """测试已完成的主题不会重复触发回调"""
    callback, called = completion_callback_called
    topic_tracker.on_completion(callback)

    # 添加并完成任务
    topic_tracker.add_task(sample_task)
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED)
    assert called["count"] == 1

    # 再次更新状态
    await topic_tracker.update_task_status(sample_task.id, TaskStatus.COMPLETED)
    assert called["count"] == 1  # 回调不应该被再次触发
