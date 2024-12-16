"""最小MVP示例，测试对话->对话池->任务队列的基本流程。"""

from uuid import UUID
from datetime import datetime, timezone, timedelta

from Opera.core.intent_mind import IntentMind
from Opera.signalr_client.opera_signalr_client import MessageReceivedArgs

def main():
    # 1. 创建一个Bot的意图处理器
    intent_mind = IntentMind()
    opera_id = UUID('96028f82-9f76-4372-976c-f0c5a054db79')
    receiver_staff_ids = [UUID('c2a71833-4403-4d08-8ef6-23e6327832b2')]
    sender_staff_id = UUID('ab01d4f7-bbf1-44aa-a55b-cbc7d62fbfbc')
    # 2. 创建一个模拟的消息
    message = MessageReceivedArgs(
        opera_id=opera_id,
        receiver_staff_ids=receiver_staff_ids,
        index=1,
        text="写一个python代码，计算1到100的和",
        sender_staff_id=sender_staff_id,
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