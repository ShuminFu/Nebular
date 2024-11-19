class ConversationManager:
    def __init__(self, autogen_config: Dict):
        self.agents = {}
        self.config = autogen_config
        
    async def start_conversation(self, participants: List[str]):
        # 直接使用Autogen API
        group = GroupChat(
            agents=[self.agents[p] for p in participants]
        )
        return group