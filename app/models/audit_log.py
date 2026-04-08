from datetime import datetime

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


def agora_brasil():
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        except ZoneInfoNotFoundError:
            pass
        except Exception:
            pass

    return datetime.now()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    entity_version = Column(Integer, nullable=False, default=1)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=agora_brasil, nullable=False, index=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} entity_type='{self.entity_type}' "
            f"entity_id={self.entity_id} action='{self.action}'>"
        )
