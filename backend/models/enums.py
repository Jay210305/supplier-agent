from enum import Enum


class PurchaseOrderStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    SENT = "SENT"


class LogSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
