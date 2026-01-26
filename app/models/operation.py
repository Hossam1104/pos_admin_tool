"""
Data models for structured operation results
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class OperationStatus(Enum):
    """Status of an operation"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResourceType(Enum):
    """Type of affected resource"""

    SERVICE = "service"
    DATABASE = "database"
    FOLDER = "folder"
    FILE = "file"
    REGISTRY_KEY = "registry_key"
    PROCESS = "process"


@dataclass
class Resource:
    """Represents a system resource"""

    type: ResourceType
    name: str
    path: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    """Structured result of an operation"""

    operation: str
    status: OperationStatus
    start_time: datetime
    end_time: Optional[datetime] = None

    # Detailed results
    success: bool = False
    partial_success: bool = False

    # Messages and errors
    messages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Affected resources
    affected_resources: List[Resource] = field(default_factory=list)

    # Metrics
    duration_seconds: Optional[float] = None

    # Additional context
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate duration if end_time is set"""
        if self.end_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def add_message(self, message: str):
        """Add an informational message"""
        self.messages.append(message)

    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def add_resource(self, resource: Resource):
        """Add an affected resource"""
        self.affected_resources.append(resource)

    def finalize(self, status: OperationStatus):
        """Finalize the operation result"""
        self.end_time = datetime.now()
        self.status = status

        # Determine overall success
        if status == OperationStatus.SUCCESS:
            self.success = True
            self.partial_success = False
        elif status == OperationStatus.PARTIAL_SUCCESS:
            self.success = False
            self.partial_success = True
        else:
            self.success = False
            self.partial_success = False

        # Calculate duration
        self.__post_init__()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "operation": self.operation,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "success": self.success,
            "partial_success": self.partial_success,
            "messages": self.messages,
            "errors": self.errors,
            "warnings": self.warnings,
            "affected_resources_count": len(self.affected_resources),
            "duration_seconds": self.duration_seconds,
            "has_errors": len(self.errors) > 0,
            "has_warnings": len(self.warnings) > 0,
        }

    @classmethod
    def create(cls, operation: str) -> "OperationResult":
        """Create a new operation result"""
        return cls(
            operation=operation,
            status=OperationStatus.PENDING,
            start_time=datetime.now(),
        )

    def is_complete(self) -> bool:
        """Check if operation is complete"""
        return self.status in [
            OperationStatus.SUCCESS,
            OperationStatus.PARTIAL_SUCCESS,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        ]
