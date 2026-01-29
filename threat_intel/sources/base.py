# threat_intel/sources/base.py
from abc import ABC, abstractmethod

class BaseConnector(ABC):
    code: str

    @abstractmethod
    def fetch(self, start_dt, end_dt, cursor=None) -> tuple[list[dict], dict]:
        """
        Return: (items, new_cursor)
        item = {
          "external_id": str,
          "published_at": datetime|None,
          "url": str,
          "title": str,
          "payload": dict
        }
        """
        raise NotImplementedError
