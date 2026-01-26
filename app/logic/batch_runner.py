"""
Executes batch-equivalent commands with proper error handling and timeouts
"""

import subprocess
import os
import shutil
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime
import logging

from app.utils.logger import get_logger
from app.models import OperationResult, Resource, ResourceType, OperationStatus

logger = get_logger()


class BatchRunner:
    """Executes commands equivalent to the original batch files"""

    # Timeout constants (seconds)
    COMMAND_TIMEOUT = 300  # 5 minutes for long-running commands
    SERVICE_TIMEOUT = 60  # 1 minute for service operations
    SQL_TIMEOUT = 600  # 10 minutes for database operations

    def __init__(self, config_manager):
        self.config = config_manager
        self.output_callback = None

    def set_output_callback(self, callback):
        """Set callback for real-time output"""
        self.output_callback = callback

    def _log_output(self, message: str, is_error: bool = False):
        """Log output and send to callback"""
        if is_error:
            logger.error(message)
        else:
            logger.info(message)

        if self.output_callback:
            self.output_callback(message, is_error)

    def run_command(
        self,
        command: List[str],
        shell: bool = False,
        timeout: Optional[int] = COMMAND_TIMEOUT,
    ) -> Tuple[int, str, str]:
        """Execute a command with timeout and return results"""
        try:
            # Mask sensitive data in command for logging
            log_command = self._mask_sensitive_data(" ".join(command))
            self._log_output(f"Executing: {log_command}")

            start_time = time.time()

            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )

            duration = time.time() - start_time
            logger.info(
                f"Command completed in {duration:.2f}s with return code: {result.returncode}"
            )

            if result.stdout:
                # Mask sensitive data in output
                safe_output = self._mask_sensitive_data(result.stdout)
                self._log_output(safe_output)
            if result.stderr:
                safe_stderr = self._mask_sensitive_data(result.stderr)
                self._log_output(safe_stderr, is_error=True)

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout}s: {e}"
            self._log_output(error_msg, is_error=True)
            return 1, "", error_msg
        except Exception as e:
            error_msg = f"Command execution failed: {e}"
            self._log_output(error_msg, is_error=True)
            return 1, "", error_msg

    def _mask_sensitive_data(self, text: str) -> str:
        """Mask passwords and other sensitive data in log output"""
        if not text:
            return text

        # Get SQL password for masking
        sql_password = self.config.get("sql_password")
        if sql_password and len(sql_password) > 3:
            # Replace password with asterisks
            text = text.replace(sql_password, "***")

        # Also mask common password patterns in commands
        import re

        # Mask -P password arguments
        text = re.sub(r"(-P\s+)([^\s]+)", r"\1***", text)

        return text

    def sqlcmd(
        self, query: str, database: str = "master", timeout: Optional[int] = None
    ) -> Tuple[int, str, str]:
        """Execute SQL query using sqlcmd with timeout"""
        if timeout is None:
            timeout = self.SQL_TIMEOUT

        sql_instance = self.config.get("sql_instance")
        sql_user = self.config.get("sql_user")
        sql_password = self.config.get("sql_password")

        # Validate we have credentials
        if not sql_password:
            logger.error("SQL password not available")
            return 1, "", "SQL password not configured"

        cmd = [
            "sqlcmd",
            "-S",
            sql_instance,
            "-U",
            sql_user,
            "-P",
            sql_password,
            "-d",
            database,
            "-Q",
            query,
            "-b",  # Exit on error
        ]

        return self.run_command(cmd, timeout=timeout)

    # ===== CLEANUP OPERATIONS WITH STRUCTURED RESULTS =====

    def stop_service(self, service_name: str) -> Tuple[bool, str]:
        """Stop a Windows service with timeout"""
        self._log_output(f"[*] Stopping service: {service_name}")

        try:
            returncode, stdout, stderr = self.run_command(
                ["net", "stop", service_name], timeout=self.SERVICE_TIMEOUT
            )

            # Return code 0 = success, 2 = service not running
            success = returncode in [0, 2]
            message = (
                f"Service {service_name} stopped"
                if success
                else f"Failed to stop service {service_name}"
            )

            return success, message

        except Exception as e:
            error_msg = f"Error stopping service {service_name}: {e}"
            self._log_output(error_msg, is_error=True)
            return False, error_msg

    def delete_service(self, service_name: str) -> Tuple[bool, str]:
        """Delete a Windows service"""
        self._log_output(f"[*] Deleting service: {service_name}")

        try:
            returncode, stdout, stderr = self.run_command(
                ["sc", "delete", service_name]
            )
            success = returncode == 0
            message = (
                f"Service {service_name} deleted"
                if success
                else f"Failed to delete service {service_name}"
            )

            return success, message

        except Exception as e:
            error_msg = f"Error deleting service {service_name}: {e}"
            self._log_output(error_msg, is_error=True)
            return False, error_msg

    def drop_database(self, database_name: str) -> Tuple[bool, str]:
        """Drop a SQL Server database"""
        self._log_output(f"[*] Dropping database: {database_name}")

        try:
            returncode, stdout, stderr = self.sqlcmd(
                f"DROP DATABASE IF EXISTS [{database_name}]"
            )
            success = returncode == 0
            message = (
                f"Database {database_name} dropped"
                if success
                else f"Failed to drop database {database_name}"
            )

            return success, message

        except Exception as e:
            error_msg = f"Error dropping database {database_name}: {e}"
            self._log_output(error_msg, is_error=True)
            return False, error_msg

    def delete_folder(self, folder_path: str) -> Tuple[bool, str]:
        """Delete a folder recursively"""
        folder = Path(folder_path)
        if not folder.exists():
            return True, f"Folder does not exist: {folder}"

        try:
            self._log_output(f"[*] Deleting folder: {folder}")
            shutil.rmtree(folder)
            return True, f"Folder deleted: {folder}"

        except Exception as e:
            error_msg = f"Failed to delete folder {folder}: {e}"
            self._log_output(error_msg, is_error=True)
            return False, error_msg

    def cleanup_registry(self) -> Tuple[bool, str, List[str]]:
        """Clean registry uninstall entries and RMS_ folders"""
        self._log_output("[*] Cleaning registry uninstall entries and RMS_ folders...")

        errors = []

        try:
            # PowerShell command equivalent to batch file
            script_path = (
                Path(__file__).parent.parent.parent
                / "assets"
                / "scripts"
                / "cleanup_registry.ps1"
            )

            if not script_path.exists():
                error_msg = f"Script not found: {script_path}"
                self._log_output(error_msg, is_error=True)
                return False, error_msg, [error_msg]

            with open(script_path, "r") as f:
                ps_script = f.read()

            cmd = ["powershell", "-nologo", "-noprofile", "-Command", ps_script]
            returncode, stdout, stderr = self.run_command(cmd)

            if stdout:
                self._log_output(stdout)
            if stderr and "ErrorAction" not in stderr:
                errors.append(stderr)
                self._log_output(stderr, is_error=True)

            success = returncode == 0
            message = (
                "Registry cleanup completed" if success else "Registry cleanup failed"
            )

            return success, message, errors

        except Exception as e:
            error_msg = f"Registry cleanup failed: {e}"
            self._log_output(error_msg, is_error=True)
            return False, error_msg, [error_msg]

    def execute_cleanup(self) -> OperationResult:
        """Execute the complete cleanup operation with structured results"""
        result = OperationResult.create("cleanup")
        result.status = OperationStatus.RUNNING

        self._log_output("Starting cleanup operation...")
        result.add_message("Cleanup operation started")

        # Stop and delete services
        services = self.config.get("services")
        service_results = []

        for service in services:
            # Stop service
            success, message = self.stop_service(service)
            resource = Resource(
                type=ResourceType.SERVICE,
                name=service,
                additional_info={"action": "stop", "success": success},
            )
            result.add_resource(resource)

            if success:
                result.add_message(f"Service stopped: {service}")
            else:
                result.add_warning(f"Failed to stop service: {service}")

            # Delete service
            success, message = self.delete_service(service)
            resource = Resource(
                type=ResourceType.SERVICE,
                name=service,
                additional_info={"action": "delete", "success": success},
            )
            result.add_resource(resource)

            if success:
                result.add_message(f"Service deleted: {service}")
            else:
                result.add_error(f"Failed to delete service: {service}")

            service_results.append(success)

        # Drop databases
        databases = self.config.get("databases")
        db_results = []

        for db in databases:
            success, message = self.drop_database(db)
            resource = Resource(
                type=ResourceType.DATABASE,
                name=db,
                additional_info={"action": "drop", "success": success},
            )
            result.add_resource(resource)

            if success:
                result.add_message(f"Database dropped: {db}")
            else:
                result.add_error(f"Failed to drop database: {db}")

            db_results.append(success)

        # Delete folders
        folders = self.config.get("folders_to_delete")
        folder_results = []

        for folder in folders:
            success, message = self.delete_folder(folder)
            resource = Resource(
                type=ResourceType.FOLDER,
                name=folder,
                additional_info={"action": "delete", "success": success},
            )
            result.add_resource(resource)

            if success:
                result.add_message(f"Folder deleted: {folder}")
            else:
                result.add_warning(f"Failed to delete folder: {folder}")

            folder_results.append(success)

        # Clean registry
        registry_success, registry_message, registry_errors = self.cleanup_registry()
        resource = Resource(
            type=ResourceType.REGISTRY_KEY,
            name="RMS_RegistryEntries",
            additional_info={"action": "cleanup", "success": registry_success},
        )
        result.add_resource(resource)

        if registry_success:
            result.add_message("Registry cleanup completed")
        else:
            for error in registry_errors:
                result.add_error(f"Registry error: {error}")

        # Determine overall status
        all_errors = result.errors
        all_warnings = result.warnings

        if not all_errors:
            result.finalize(OperationStatus.SUCCESS)
            self._log_output("[✔] Cleanup and deletion complete.")
        elif all_errors and len(all_errors) < len(service_results) + len(
            db_results
        ) + len(folder_results):
            result.finalize(OperationStatus.PARTIAL_SUCCESS)
            self._log_output("[!] Cleanup completed with some errors.")
        else:
            result.finalize(OperationStatus.FAILED)
            self._log_output("[✗] Cleanup failed.")

        return result

    # ===== RESTORE OPERATIONS WITH STRUCTURED RESULTS =====

    def execute_restore(
        self, client_name: str, db_choice: str, backup_path: str
    ) -> OperationResult:
        """Execute database restore operation with structured results"""
        result = OperationResult.create("restore")
        result.status = OperationStatus.RUNNING

        # Determine target database
        if db_choice == "1":
            base_db = "RmsBranchSrv"
        else:
            base_db = "RmsCashierSrv"

        target_db = f"{client_name}_{base_db}"

        self._log_output(f"Starting restore operation for: {target_db}")
        self._log_output(f"Backup file: {backup_path}")

        result.add_message(f"Restoring {target_db} from {backup_path}")

        # Validate backup file exists
        if not Path(backup_path).exists():
            result.add_error(f"Backup file not found: {backup_path}")
            result.finalize(OperationStatus.FAILED)
            return result

        # Get SQL paths
        data_path, log_path = self.get_sql_paths()
        if not data_path or not log_path:
            error_msg = "Cannot determine DATA/LOG paths."
            result.add_error(error_msg)
            self._log_output(f"[ERROR] {error_msg}", is_error=True)
            result.finalize(OperationStatus.FAILED)
            return result

        # Get logical file names
        logical_data, logical_log = self.get_backup_filelist(backup_path)
        if not logical_data or not logical_log:
            error_msg = "Could not read logical files from backup."
            result.add_error(error_msg)
            self._log_output(f"[ERROR] {error_msg}", is_error=True)
            result.finalize(OperationStatus.FAILED)
            return result

        # Build target paths
        target_mdf = f"{data_path}{target_db}.mdf"
        target_ldf = f"{log_path}{target_db}_log.ldf"

        # Escape paths for SQL
        escaped_backup = backup_path.replace("'", "''")
        escaped_mdf = target_mdf.replace("'", "''")
        escaped_ldf = target_ldf.replace("'", "''")

        # Drop existing database if it exists
        drop_query = f"""
        IF DB_ID(N'{target_db}') IS NOT NULL
        BEGIN
            PRINT 'Dropping existing [{target_db}]...';
            ALTER DATABASE [{target_db}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
            DROP DATABASE [{target_db}];
        END;
        """

        returncode, stdout, stderr = self.sqlcmd(drop_query)
        if returncode != 0:
            warning_msg = "Failed to drop existing database (may not exist)"
            result.add_warning(warning_msg)
            self._log_output(f"[WARN] {warning_msg}", is_error=False)

        # Restore database
        restore_query = f"""
        PRINT 'RESTORE starting...';
        RESTORE DATABASE [{target_db}]
          FROM DISK = N'{escaped_backup}'
          WITH MOVE N'{logical_data}' TO N'{escaped_mdf}',
               MOVE N'{logical_log}'  TO N'{escaped_ldf}',
               REPLACE, RECOVERY, STATS = 5;
        PRINT 'RESTORE complete.';
        """

        self._log_output(f"Restoring to [{target_db}] ...")
        returncode, stdout, stderr = self.sqlcmd(restore_query)

        if returncode == 0:
            success_msg = "Database restore successful"
            self._log_output("===== SUCCESS =====")
            self._log_output(f"DB: [{target_db}]")
            self._log_output(f"MDF: {target_mdf}")
            self._log_output(f"LDF: {target_ldf}")

            result.add_message(success_msg)
            result.add_resource(
                Resource(
                    type=ResourceType.DATABASE,
                    name=target_db,
                    path=target_mdf,
                    additional_info={
                        "data_file": target_mdf,
                        "log_file": target_ldf,
                        "source_backup": backup_path,
                    },
                )
            )

            result.finalize(OperationStatus.SUCCESS)
            return result
        else:
            error_msg = "Database restore failed"
            self._log_output("[ERROR] Restore failed", is_error=True)
            result.add_error(error_msg)
            result.finalize(OperationStatus.FAILED)
            return result

    # ===== BACKUP OPERATIONS WITH STRUCTURED RESULTS =====

    def execute_backup(self) -> OperationResult:
        """Execute shrink and backup operation with structured results"""
        result = OperationResult.create("backup")
        result.status = OperationStatus.RUNNING

        timestamp = datetime.now().strftime("%d-%m-%Y_%I-%M-%S-%p")
        backup_folder = self.config.get("backup_folder")
        temp_dir = Path(backup_folder) / "Temp"

        # Create directories
        temp_dir.mkdir(parents=True, exist_ok=True)

        self._log_output("[*] Creating temporary backup directory...")
        result.add_message(f"Backup directory: {temp_dir}")

        # Shrink and backup databases
        databases = self.config.get("databases")
        backup_results = []

        for db in databases:
            self._log_output(f"[*] Shrinking database: {db}")
            shrink_success = self.shrink_database(db)

            if shrink_success:
                result.add_message(f"Database shrunk: {db}")
            else:
                result.add_warning(f"Failed to shrink database: {db}")

            backup_path = temp_dir / f"{db}_{timestamp}.bak"
            self._log_output(f"[*] Backing up database: {db}")
            backup_success = self.backup_database(db, str(backup_path))

            resource = Resource(
                type=ResourceType.DATABASE,
                name=db,
                path=str(backup_path),
                additional_info={
                    "action": "backup",
                    "shrink_success": shrink_success,
                    "backup_success": backup_success,
                    "backup_size": (
                        backup_path.stat().st_size if backup_path.exists() else 0
                    ),
                },
            )
            result.add_resource(resource)

            if backup_success:
                result.add_message(f"Database backed up: {db}")
                backup_results.append(True)
            else:
                result.add_error(f"Failed to backup database: {db}")
                backup_results.append(False)

        # Copy appsettings files
        self._log_output("[*] Copying and timestamping appsettings.json files...")
        appsettings = self.config.get("appsettings_files")
        appsettings_results = []

        for item in appsettings:
            copy_success = self.copy_appsettings(
                item["path"], item["name"], timestamp, str(temp_dir)
            )

            resource = Resource(
                type=ResourceType.FILE,
                name=item["name"],
                path=item["path"],
                additional_info={"action": "copy", "success": copy_success},
            )
            result.add_resource(resource)

            if copy_success:
                result.add_message(f"File copied: {item['name']}")
                appsettings_results.append(True)
            else:
                result.add_warning(f"Failed to copy file: {item['name']}")
                appsettings_results.append(False)

        # Create ZIP file
        zip_file = (
            Path(backup_folder) / f"POS_LocalDB_Appsettings_Backup_{timestamp}.zip"
        )

        self._log_output("[*] Compressing backup into ZIP...")
        try:
            import zipfile

            with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file():
                        zipf.write(file_path, file_path.relative_to(temp_dir))

            zip_success = zip_file.exists()

            if zip_success:
                result.add_message(f"ZIP archive created: {zip_file}")
                result.add_resource(
                    Resource(
                        type=ResourceType.FILE,
                        name=zip_file.name,
                        path=str(zip_file),
                        additional_info={"action": "create", "success": True},
                    )
                )
            else:
                result.add_error("Failed to create ZIP archive")

            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
                result.add_message("Temporary directory cleaned up")
            except Exception as e:
                result.add_warning(f"Failed to cleanup temp directory: {e}")

            self._log_output(f"[✔] Backup complete: {zip_file}")

            # Open backup folder
            if os.name == "nt" and zip_success:
                try:
                    os.startfile(backup_folder)
                    result.add_message("Backup folder opened")
                except Exception as e:
                    result.add_warning(f"Failed to open backup folder: {e}")

            # Determine overall status
            if all(backup_results) and zip_success:
                result.finalize(OperationStatus.SUCCESS)
            elif any(backup_results) and zip_success:
                result.finalize(OperationStatus.PARTIAL_SUCCESS)
            else:
                result.finalize(OperationStatus.FAILED)

            result.context["zip_file"] = str(zip_file)
            return result

        except Exception as e:
            error_msg = f"Failed to create ZIP: {e}"
            self._log_output(error_msg, is_error=True)
            result.add_error(error_msg)
            result.finalize(OperationStatus.FAILED)
            return result

    # ===== HELPER METHODS (keep existing functionality) =====

    def get_backup_files(self, directory: str) -> List[Dict[str, str]]:
        """Get list of .bak files in directory"""
        backup_dir = Path(directory)
        if not backup_dir.exists():
            return []

        files = []
        for bak_file in backup_dir.glob("*.bak"):
            files.append(
                {
                    "path": str(bak_file),
                    "name": bak_file.name,
                    "size": bak_file.stat().st_size,
                }
            )

        return files

    def get_sql_paths(self) -> Tuple[str, str]:
        """Get default SQL Server DATA and LOG paths"""
        query = """
        SET NOCOUNT ON;
        DECLARE @d nvarchar(260)=CAST(SERVERPROPERTY('InstanceDefaultDataPath') as nvarchar(260));
        DECLARE @l nvarchar(260)=CAST(SERVERPROPERTY('InstanceDefaultLogPath')  as nvarchar(260));
        IF @d IS NULL
            SELECT TOP(1) @d = LEFT(physical_name, LEN(physical_name)-CHARINDEX('\', REVERSE(physical_name))+1)
            FROM master.sys.master_files WHERE database_id=1 AND type=0;
        IF @l IS NULL
            SELECT TOP(1) @l = LEFT(physical_name, LEN(physical_name)-CHARINDEX('\', REVERSE(physical_name))+1)
            FROM master.sys.master_files WHERE database_id=1 AND type=1;
        SELECT @d AS DataPath, @l AS LogPath;
        """

        returncode, stdout, stderr = self.sqlcmd(query)

        if returncode != 0 or not stdout:
            return "", ""

        # Parse output
        lines = stdout.strip().split("\n")
        for line in lines:
            if "|" in line:
                data_path, log_path = line.split("|")
                return data_path.strip(), log_path.strip()

        return "", ""

    def get_backup_filelist(self, backup_path: str) -> Tuple[str, str]:
        """Get logical file names from backup"""
        # Escape single quotes for T-SQL
        escaped_path = backup_path.replace("'", "''")

        query = f"SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK = N'{escaped_path}';"
        returncode, stdout, stderr = self.sqlcmd(query)

        if returncode != 0:
            return "", ""

        logical_data = ""
        logical_log = ""

        lines = stdout.strip().split("\n")
        for line in lines:
            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 4:
                    logical_name = parts[0].strip()
                    file_type = parts[2].strip()
                    if file_type == "D" and not logical_data:
                        logical_data = logical_name
                    elif file_type == "L" and not logical_log:
                        logical_log = logical_name

        return logical_data, logical_log

    def shrink_database(self, database_name: str) -> bool:
        """Shrink a database using DBCC SHRINKDATABASE"""
        query = f"DBCC SHRINKDATABASE (N'{database_name}', TRUNCATEONLY)"
        returncode, stdout, stderr = self.sqlcmd(query)
        return returncode == 0

    def backup_database(self, database_name: str, backup_path: str) -> bool:
        """Backup a database to specified path"""
        query = f"BACKUP DATABASE [{database_name}] TO DISK = '{backup_path}' WITH COMPRESSION"
        returncode, stdout, stderr = self.sqlcmd(query)
        return returncode == 0

    def copy_appsettings(
        self, source_path: str, target_name: str, timestamp: str, temp_dir: str
    ) -> bool:
        """Copy and timestamp appsettings file"""
        source = Path(source_path)
        if not source.exists():
            self._log_output(f"File not found: {source_path}")
            return False

        # Create target filename with timestamp
        target_stem = Path(target_name).stem
        target_ext = Path(target_name).suffix
        target_filename = f"{target_stem}_{timestamp}{target_ext}"
        target_path = Path(temp_dir) / target_filename

        try:
            shutil.copy2(source, target_path)
            self._log_output(f"  - Copying: {source_path} → {target_filename}")
            return True
        except Exception as e:
            self._log_output(f"Failed to copy {source_path}: {e}", is_error=True)
            return False
