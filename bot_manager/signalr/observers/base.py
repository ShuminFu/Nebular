from abc import ABC, abstractmethod
from typing import Any

class IMessageObserver(ABC):
    @abstractmethod
    async def update(self, message: Any) -> None:
        pass

class SignalRMessageSubject:
    def __init__(self):
        self._observers = []
    
    def attach(self, observer: IMessageObserver) -> None:
        self._observers.append(observer)
        
    def detach(self, observer: IMessageObserver) -> None:
        self._observers.remove(observer)
        
    async def notify(self, message: Any) -> None:
        for observer in self._observers:
            await observer.update(message) 