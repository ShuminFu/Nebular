"""最小MVP示例，测试对话->对话池->任务队列的基本流程。"""

from uuid import UUID
from datetime import datetime, timezone, timedelta

from Opera.core.intent_mind import IntentMind
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs

def main():
    # 1. 创建一个Bot的意图处理器
    bot_id = UUID('550e8400-e29b-41d4-a716-446655440000')  # 示例UUID
    intent_mind = IntentMind(bot_id=bot_id)
    
    # 2. 创建一个模拟的消息
    message = MessageReceivedArgs(
        index=1,
        text="请帮我分析最近的销售数据",
        sender_staff_id=UUID('660e8400-e29b-41d4-a716-446655440000'),  # 示例Staff UUID
        time=datetime.now(timezone(timedelta(hours=8))),
        is_narratage=False,
        is_whisper=False,
        tags="query, urgent",
        mentioned_staff_ids=[],
        stage_index=None
    )
    
    # 3. 处理消息
    print("处理消息...")
    intent_mind.process_message(message)
    
    # 4. 检查对话池状态
    dialogue_pool = intent_mind.get_dialogue_pool()
    print("\n对话池状态:")
    print(f"- 对话数量: {len(dialogue_pool.dialogues)}")
    print(f"- 状态计数: {dialogue_pool.status_counter}")
    
    # 5. 检查第一个对话的详细信息
    if dialogue_pool.dialogues:
        dialogue = dialogue_pool.dialogues[0]
        print("\n对话详情:")
        print(f"- 索引: {dialogue.dialogue_index}")
        print(f"- 优先级: {dialogue.priority}")
        print(f"- 类型: {dialogue.type}")
        print(f"- 状态: {dialogue.status}")
        if dialogue.intent_analysis:
            print(f"- 意图: {dialogue.intent_analysis.intent}")
            print(f"- 置信度: {dialogue.intent_analysis.confidence}")
    
    # 6. 检查任务队列状态
    task_queue = intent_mind.get_task_queue()
    print("\n任务队列状态:")
    print(f"- 任务数量: {len(task_queue.tasks)}")
    print(f"- 状态计数: {task_queue.status_counter}")
    
    # 7. 检查第一个任务的详细信息
    if task_queue.tasks:
        task = task_queue.tasks[0]
        print("\n任务详情:")
        print(f"- ID: {task.id}")
        print(f"- 优先级: {task.priority}")
        print(f"- 类型: {task.type}")
        print(f"- 状态: {task.status}")
        print(f"- 描述: {task.description}")
        print(f"- 源对话索引: {task.source_dialogue_index}")
        print(f"- 源Staff ID: {task.source_staff_id}")

if __name__ == "__main__":
    main() 