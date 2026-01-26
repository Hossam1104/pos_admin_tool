"""
Thread-safe worker for executing operations
"""

import time
from typing import Optional
from PySide6.QtCore import QThread, Signal

from app.logic.batch_runner import BatchRunner
from app.models import OperationResult, OperationStatus
from app.utils.logger import get_logger

logger = get_logger()


class WorkerThread(QThread):
    """Worker thread for long-running operations with thread safety"""

    # Signals for UI updates
    operation_started = Signal(str)  # operation_name
    output_received = Signal(str, bool)  # message, is_error
    operation_progress = Signal(str, int, int)  # operation, current, total
    operation_complete = Signal(OperationResult)

    def __init__(self, operation_type: str, runner: BatchRunner, **kwargs):
        super().__init__()
        self.operation_type = operation_type
        self.runner = runner
        self.kwargs = kwargs
        self._is_cancelled = False

        # Connect runner output to our signals
        self.runner.set_output_callback(self._handle_output)

    def _handle_output(self, message: str, is_error: bool = False):
        """Handle output from batch runner and forward via signal"""
        self.output_received.emit(message, is_error)

    def cancel(self):
        """Cancel the operation"""
        self._is_cancelled = True

    def run(self):
        """Execute the operation in a separate thread"""
        try:
            logger.info(f"Starting {self.operation_type} operation")
            self.operation_started.emit(self.operation_type)

            if self._is_cancelled:
                result = OperationResult.create(self.operation_type)
                result.add_message("Operation cancelled before start")
                result.finalize(OperationStatus.CANCELLED)
                self.operation_complete.emit(result)
                return

            if self.operation_type == "cleanup":
                result = self.runner.execute_cleanup()

            elif self.operation_type == "restore":
                result = self.runner.execute_restore(
                    self.kwargs.get("client_name"),
                    self.kwargs.get("db_choice"),
                    self.kwargs.get("backup_path"),
                )

            elif self.operation_type == "backup":
                result = self.runner.execute_backup()

            else:
                result = OperationResult.create(self.operation_type)
                result.add_error(f"Unknown operation: {self.operation_type}")
                result.finalize(OperationStatus.FAILED)

            # Emit completion signal
            self.operation_complete.emit(result)

            # Log completion
            status_msg = {
                OperationStatus.SUCCESS: "completed successfully",
                OperationStatus.PARTIAL_SUCCESS: "completed with warnings",
                OperationStatus.FAILED: "failed",
                OperationStatus.CANCELLED: "cancelled",
            }.get(result.status, "completed")

            logger.info(f"{self.operation_type} operation {status_msg}")

        except Exception as e:
            logger.error(f"Error in worker thread: {e}", exc_info=True)

            # Create error result
            result = OperationResult.create(self.operation_type)
            result.add_error(f"Unexpected error: {e}")
            result.finalize(OperationStatus.FAILED)
            self.operation_complete.emit(result)
