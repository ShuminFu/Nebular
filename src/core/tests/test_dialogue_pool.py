import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core.dialogue.enums import ProcessingStatus, DialogueType
from src.core.dialogue.models import ProcessingDialogue, DialogueContext
from src.core.dialogue.pools import DialoguePool


@pytest.fixture
def mock_dialogue():
    """创建测试用对话"""
    return ProcessingDialogue(
        dialogue_index=1,
        opera_id=uuid4(),
        receiver_staff_ids=[uuid4()],
        content="测试对话内容",
        created_at=datetime.now(timezone(timedelta(hours=8))),
        status=ProcessingStatus.PENDING,
        context=DialogueContext(stage_index=None),
        heat=1.0,
        type=DialogueType.NORMAL,
    )


@pytest.fixture
def mock_dialogue_pool():
    """创建测试用对话池"""
    return DialoguePool()


class TestDialoguePool:
    """测试DialoguePool类"""

    async def test_add_dialogue_triggers_analysis(self, mock_dialogue_pool, mock_dialogue):
        """测试添加对话时正确触发分析标记"""
        # 添加对话
        await mock_dialogue_pool.add_dialogue(mock_dialogue)

        # 验证分析状态
        state = mock_dialogue_pool.opera_analysis_state[mock_dialogue.opera_id]
        assert state["needs_analysis"] is True
        assert state["last_analyzed_at"] is None

    async def test_add_multiple_dialogues_same_opera(self, mock_dialogue_pool, mock_dialogue):
        """测试添加多个相同Opera的对话"""
        # 添加第一个对话
        await mock_dialogue_pool.add_dialogue(mock_dialogue)

        # 创建同一个Opera的第二个对话
        second_dialogue = ProcessingDialogue(
            dialogue_index=2,
            opera_id=mock_dialogue.opera_id,  # 使用相同的opera_id
            receiver_staff_ids=[uuid4()],
            content="第二条测试对话",
            created_at=datetime.now(timezone(timedelta(hours=8))),
            status=ProcessingStatus.PENDING,
            context=DialogueContext(stage_index=None),
            heat=1.0,
            type=DialogueType.NORMAL,  # 添加必需的 type 字段
        )
        await mock_dialogue_pool.add_dialogue(second_dialogue)

        # 验证分析状态
        state = mock_dialogue_pool.opera_analysis_state[mock_dialogue.opera_id]
        assert state["needs_analysis"] is True
        assert len(mock_dialogue_pool.dialogues) == 2

    def test_analyze_dialogues_basic(self, mock_dialogue_pool, mock_dialogue):
        """测试基本的对话分析功能"""
        # 添加对话到池中
        mock_dialogue_pool.dialogues.append(mock_dialogue)
        mock_dialogue_pool.opera_analysis_state[mock_dialogue.opera_id] = {"last_analyzed_at": None, "needs_analysis": True}

        # 执行分析
        mock_dialogue_pool.analyze_dialogues()

        # 验证分析状态被更新
        state = mock_dialogue_pool.opera_analysis_state[mock_dialogue.opera_id]
        assert state["needs_analysis"] is False
        assert state["last_analyzed_at"] is not None

    def test_analyze_dialogues_target_opera(self, mock_dialogue_pool):
        """测试针对特定Opera的分析"""
        # 创建两个不同Opera的对话
        opera1_id = uuid4()
        opera2_id = uuid4()

        dialogue1 = ProcessingDialogue(
            dialogue_index=1,
            opera_id=opera1_id,
            receiver_staff_ids=[uuid4()],
            content="Opera1的对话",
            created_at=datetime.now(timezone(timedelta(hours=8))),
            status=ProcessingStatus.PENDING,
            context=DialogueContext(stage_index=None),
            heat=1.0,
            type=DialogueType.NORMAL,  # 添加必需的 type 字段
        )

        dialogue2 = ProcessingDialogue(
            dialogue_index=2,
            opera_id=opera2_id,
            receiver_staff_ids=[uuid4()],
            content="Opera2的对话",
            created_at=datetime.now(timezone(timedelta(hours=8))),
            status=ProcessingStatus.PENDING,
            context=DialogueContext(stage_index=None),
            heat=1.0,
            type=DialogueType.NORMAL,  # 添加必需的 type 字段
        )

        # 添加对话到池中
        mock_dialogue_pool.dialogues.extend([dialogue1, dialogue2])
        mock_dialogue_pool.opera_analysis_state.update({
            opera1_id: {"last_analyzed_at": None, "needs_analysis": True},
            opera2_id: {"last_analyzed_at": None, "needs_analysis": True},
        })

        # 只分析Opera1
        mock_dialogue_pool.analyze_dialogues(target_opera_id=opera1_id)

        # 验证只有Opera1被分析
        assert mock_dialogue_pool.opera_analysis_state[opera1_id]["needs_analysis"] is False
        assert mock_dialogue_pool.opera_analysis_state[opera2_id]["needs_analysis"] is True

    async def test_clean_expired_dialogues_triggers_analysis(self, mock_dialogue_pool, mock_dialogue):
        """测试清理过期对话时触发分析"""
        # 添加一个即将过期的对话
        old_dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=uuid4(),
            receiver_staff_ids=[uuid4()],
            content="过期对话",
            created_at=datetime.now(timezone(timedelta(hours=8))) - timedelta(hours=25),  # 超过24小时
            status=ProcessingStatus.PENDING,
            context=DialogueContext(stage_index=None),
            heat=1.0,
            type=DialogueType.NORMAL,  # 添加必需的 type 字段
        )
        mock_dialogue_pool.dialogues.append(old_dialogue)
        mock_dialogue_pool.opera_analysis_state[old_dialogue.opera_id] = {
            "last_analyzed_at": datetime.now(timezone(timedelta(hours=8))),
            "needs_analysis": False,
        }

        # 清理过期对话
        mock_dialogue_pool._clean_expired_dialogues()

        # 验证对话被清理且Opera被标记为需要分析
        assert len(mock_dialogue_pool.dialogues) == 0
        assert mock_dialogue_pool.opera_analysis_state[old_dialogue.opera_id]["needs_analysis"] is True

    async def test_clean_cold_dialogues_triggers_analysis(self, mock_dialogue_pool):
        """测试清理冷对话时触发分析"""
        # 创建一个冷对话
        cold_dialogue = ProcessingDialogue(
            dialogue_index=1,
            opera_id=uuid4(),
            receiver_staff_ids=[uuid4()],
            content="冷对话",
            created_at=datetime.now(timezone(timedelta(hours=8))),
            status=ProcessingStatus.PENDING,
            context=DialogueContext(stage_index=None),
            heat=0.1,  # 低于默认阈值0.5
            type=DialogueType.NORMAL,  # 添加必需的 type 字段
        )
        mock_dialogue_pool.dialogues.append(cold_dialogue)
        mock_dialogue_pool.opera_analysis_state[cold_dialogue.opera_id] = {
            "last_analyzed_at": datetime.now(timezone(timedelta(hours=8))),
            "needs_analysis": False,
        }

        # 清理冷对话
        mock_dialogue_pool._clean_cold_dialogues()

        # 验证冷对话被清理且Opera被标记为需要分析
        assert len(mock_dialogue_pool.dialogues) == 0
        assert mock_dialogue_pool.opera_analysis_state[cold_dialogue.opera_id]["needs_analysis"] is True

    def test_get_dialogue(self, mock_dialogue_pool, mock_dialogue):
        """测试获取对话功能"""
        # 添加对话到池中
        mock_dialogue_pool.dialogues.append(mock_dialogue)

        # 测试获取存在的对话
        found_dialogue = mock_dialogue_pool.get_dialogue(mock_dialogue.dialogue_index)
        assert found_dialogue is not None
        assert found_dialogue.dialogue_index == mock_dialogue.dialogue_index

        # 测试获取不存在的对话
        not_found_dialogue = mock_dialogue_pool.get_dialogue(999)
        assert not_found_dialogue is None

    async def test_update_dialogue_status(self, mock_dialogue_pool, mock_dialogue):
        """测试更新对话状态"""
        # 添加对话到池中
        mock_dialogue_pool.dialogues.append(mock_dialogue)
        initial_status = mock_dialogue.status

        # 更新状态
        new_status = ProcessingStatus.PROCESSING
        await mock_dialogue_pool.update_dialogue_status(mock_dialogue.dialogue_index, new_status)

        # 验证状态更新
        assert mock_dialogue_pool.dialogues[0].status == new_status
        assert mock_dialogue_pool.status_counter[initial_status.name.lower()] == 0
        assert mock_dialogue_pool.status_counter[new_status.name.lower()] == 1
