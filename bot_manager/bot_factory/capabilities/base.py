from abc import ABC, abstractmethod
from typing import Any

class IBotCapability(ABC):
    pass

class IRunnable(IBotCapability):
    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        pass

class IReadable(IBotCapability):
    @abstractmethod
    async def read(self, *args, **kwargs) -> Any:
        pass

class IWritable(IBotCapability):
    @abstractmethod
    async def write(self, *args, **kwargs) -> None:
        pass

class IExecutable(IBotCapability):
    @abstractmethod
    async def execute(self, command: str, *args, **kwargs) -> Any:
        pass 