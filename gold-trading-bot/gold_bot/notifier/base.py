from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, title: str, message: str, priority: str = "default") -> None: ...
