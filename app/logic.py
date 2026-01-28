"""
Executes batch-equivalent commands with proper error handling and timeouts
"""

import subprocess
import os
import shutil
import time
import requests
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime

from app.logger import get_logger
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
                creationflags=0x08000000,  # CREATE_NO_WINDOW
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

    def get_release_number(self) -> str:
        """Read the RMS+ POS Release Number from the local filesystem"""
        release_path_str = self.config.get(
            "release_path", r"C:\ProgramData\RMS_Plus\ReleaseNumber.txt"
        )
        release_path = Path(release_path_str)
        try:
            if release_path.exists():
                with open(release_path, "r") as f:
                    return f.read().strip()
            return "N/A"
        except Exception as e:
            logger.error(f"Failed to read release number: {e}")
            return "ERR"

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
            "-s",
            "|",  # Pipe delimited
            "-W",  # Strip trailing spaces
            "-h",
            "-1",  # No headers
            "-b",  # Exit on error
        ]

        return self.run_command(cmd, timeout=timeout)

    # ===== API UNINSTALL ACTIONS =====

    def _call_rms_api(
        self,
        endpoint: str,
        method: str = "POST",
        params: Dict[str, str] = None,
        json_data: Dict[str, str] = None,
    ) -> Tuple[bool, str]:
        """Helper to call RMS API with logging. Supports query params and JSON body."""

        base_url = self.config.get("api_base_url")
        if not base_url:
            return False, "API Base URL not configured"

        # Ensure base URL doesn't have trailing slash if we're adding one
        full_url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        self._log_output(f"[*] API Call ({method}): {full_url}")
        if params:
            self._log_output(f"[*] Params: {params}")
        if json_data:
            self._log_output(f"[*] Payload: {json_data}")

        try:
            # Dynamic Method Call
            # Only include json_data if it exists to avoid sending empty body/headers on GET
            req_kwargs = {"params": params, "timeout": 15}
            if json_data is not None:
                req_kwargs["json"] = json_data

            response = requests.request(method, full_url, **req_kwargs)

            self._log_output(f"    Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    self._log_output(f"    Response: {resp_json}")

                    # Check 'IsDone' from response as per requirement
                    is_done = resp_json.get("IsDone", False)
                    message = resp_json.get("Message", "Operation completed")

                    if is_done:
                        return True, message
                    else:
                        return False, f"API returned failure: {message}"

                except Exception:
                    # Fallback for non-JSON responses (legacy) or simple 200 OK
                    self._log_output(f"    Raw Response: {response.text}")
                    return True, "API call successful (No JSON)"
            else:
                error_msg = f"API Failed: {response.status_code} - {response.text}"
                self._log_output(error_msg, is_error=True)
                return False, error_msg

        except Exception as e:
            error_msg = f"API Connection Error: {e}"
            self._log_output(error_msg, is_error=True)
            return False, error_msg

    def execute_uninstall_branch(self) -> OperationResult:
        """Call Uninstall Branch API"""
        result = OperationResult.create("uninstall_branch")
        result.status = OperationStatus.RUNNING

        branch_code = self.config.get("branch_code")

        if not branch_code:
            result.add_error("Branch Code not configured")
            result.finalize(OperationStatus.FAILED)
            return result

        # Use PUT method with query params as requested: ?BranchCode=...
        # User confirmed method is PUT
        success, msg = self._call_rms_api(
            "api/Branch/UnInstalledBranch",
            method="PUT",
            params={"BranchCode": branch_code},
        )

        if success:
            result.add_message(msg)
            result.finalize(OperationStatus.SUCCESS)
        else:
            result.add_error(msg)
            result.finalize(OperationStatus.FAILED)

        return result

    def execute_uninstall_pos(self) -> OperationResult:
        """Call Uninstall POS Machine API"""
        result = OperationResult.create("uninstall_pos")
        result.status = OperationStatus.RUNNING

        branch_code = self.config.get("branch_code")
        pos_number = self.config.get("pos_number")

        if not branch_code or not pos_number:
            result.add_error("Branch Code or POS Number not configured")
            result.finalize(OperationStatus.FAILED)
            return result

        # Use PUT method with query params: ?BranchCode=...&PosNumber=...
        # User confirmed method is PUT
        success, msg = self._call_rms_api(
            "api/PosMachine/UnInstalledPos",
            method="PUT",
            params={
                "BranchCode": branch_code,
                "PosNumber": pos_number,
            },  # Note: key changed to PosNumber based on prompt
        )

        if success:
            result.add_message(msg)
            result.finalize(OperationStatus.SUCCESS)
        else:
            result.add_error(msg)
            result.finalize(OperationStatus.FAILED)

        return result

    def verify_branch_install_status(self) -> Tuple[bool, str]:
        """
        Verify if the configured Branch Code exists in the installed branches list.
        API: GET api/Branch/GetInstallBranch
        """
        branch_code = self.config.get("branch_code")
        if not branch_code:
            return False, "Branch Code not configured"

        # Call API to get list of installed branches
        # This API returns a List of Objects
        base_url = self.config.get("api_base_url")
        if not base_url:
            return False, "API Base URL not configured"

        full_url = f"{base_url.rstrip('/')}/api/Branch/GetInstallBranch"
        self._log_output(f"[*] Verifying Branch: {full_url}")

        try:
            response = requests.get(full_url, timeout=15)
            self._log_output(f"    Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    branches = response.json()
                    # Expecting a list of dicts
                    if isinstance(branches, list):
                        for b in branches:
                            if b.get("BranchCode") == branch_code:
                                return (
                                    True,
                                    f"Branch {branch_code} is Installed (ID: {b.get('Id')})",
                                )
                        return (
                            False,
                            f"Branch {branch_code} NOT found in installed list.",
                        )
                    else:
                        return False, "API returned unexpected format (not a list)"
                except Exception as e:
                    return False, f"Failed to parse API response: {e}"
            else:
                return False, f"API Failed: {response.status_code}"

        except Exception as e:
            self._log_output(f"API Error: {e}", is_error=True)
            return False, f"Connection Error: {e}"

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

    def test_sql_connection(self, instance: str, user: str, password: str) -> bool:
        """Test SQL connectivity using sqlcmd"""
        cmd = [
            "sqlcmd",
            "-S",
            instance,
            "-U",
            user,
            "-P",
            password,
            "-Q",
            "SELECT 1",
            "-b",  # On error, exit
            "-t",
            "5",  # 5 second timeout
        ]
        code, out, err = self.run_command(cmd, timeout=10)
        return code == 0

    def fetch_databases(self, instance: str, user: str, password: str) -> List[str]:
        """Fetch list of non-system databases"""
        query = "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb') ORDER BY name;"
        cmd = [
            "sqlcmd",
            "-S",
            instance,
            "-U",
            user,
            "-P",
            password,
            "-Q",
            query,
            "-h",
            "-1",  # No headers
            "-W",  # Remove trailing whitespace
            "-b",
        ]
        code, out, err = self.run_command(cmd, timeout=15)
        if code == 0 and out:
            # Parse lines, strip whitespace, ignore empty lines
            dbs = [line.strip() for line in out.splitlines() if line.strip()]
            return dbs
        return []

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
            # Correct path relative to app/logic.py (this file is app/logic.py)
            script_path = (
                Path(__file__).parent.parent
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

        if not result.errors:
            result.finalize(OperationStatus.SUCCESS)
            self._log_output("[✔] Cleanup and deletion complete.")
        elif result.errors and len(result.errors) < len(service_results) + len(
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
        self,
        backup_file: str,
        target_db: str,
        mdf_path: Optional[str] = None,
        ldf_path: Optional[str] = None,
    ) -> OperationResult:
        """Execute database restore with explicit target and paths"""
        result = OperationResult.create("restore")
        result.status = OperationStatus.RUNNING

        self._log_output(f"Starting restore operation for: {target_db}")
        self._log_output(f"Backup file: {backup_file}")

        result.add_message(f"Restoring {target_db} from {backup_file}")

        # Validate backup file exists
        if not Path(backup_file).exists():
            result.add_error(f"Backup file not found: {backup_file}")
            result.finalize(OperationStatus.FAILED)
            return result

        # Get SQL paths (Defaults or Overrides)
        default_data, default_log = self.get_sql_paths()

        # Use provided paths if available, otherwise default
        final_mdf_dir = mdf_path if mdf_path else default_data
        final_ldf_dir = ldf_path if ldf_path else default_log

        # Ensure trailing backslash
        if not final_mdf_dir.endswith("\\"):
            final_mdf_dir += "\\"
        if not final_ldf_dir.endswith("\\"):
            final_ldf_dir += "\\"

        self._log_output(f"Target MDF Path: {final_mdf_dir}")
        self._log_output(f"Target LDF Path: {final_ldf_dir}")

        # Get logical file names
        logical_data, logical_log = self.get_backup_filelist(backup_file)
        if not logical_data or not logical_log:
            error_msg = f"Could not read logical files from backup: '{backup_file}'. Verify file integrity and SQL permissions."
            result.add_error(error_msg)
            self._log_output(f"[ERROR] {error_msg}", is_error=True)
            result.finalize(OperationStatus.FAILED)
            return result

        # Build target paths
        target_mdf = f"{final_mdf_dir}{target_db}.mdf"
        target_ldf = f"{final_ldf_dir}{target_db}_log.ldf"

        # Escape paths for SQL
        escaped_backup = backup_file.replace("'", "''")
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
                        "source_backup": backup_file,
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

    def execute_backup(
        self, selected_dbs: List[str] = None, selected_appsettings: List[str] = None
    ) -> OperationResult:
        """Execute shrink and backup operation with structured results"""
        result = OperationResult.create("backup")
        result.status = OperationStatus.RUNNING
        timestamp = datetime.now().strftime("%d-%m-%Y_%I-%M-%S-%p")

        # Use defaults if not provided (Full Backup behavior)
        if selected_dbs is None:
            selected_dbs = self.config.get("databases")
        if selected_appsettings is None:
            # Match existing logic: backup all configured appsettings files
            all_settings = self.config.get("appsettings_files")
            selected_appsettings = [item["name"] for item in all_settings]

        # 0. Validate SQL Connection FIRST
        instance = self.config.get("sql_instance")
        user = self.config.get("sql_user")
        password = self.config.get("sql_password")

        if not self.test_sql_connection(instance, user, password):
            result.add_error("SQL Connection Failed. check credentials.")
            result.finalize(OperationStatus.FAILED)
            return result

        # Ensure absolute path with resolved drive root
        raw_path = self.config.get("backup_folder")
        # Fix: drive-relative paths like "C:" + "Folder" become "C:Folder"
        # We must ensure we start from root
        if len(Path(raw_path).parts) > 0 and ":" in Path(raw_path).parts[0]:
            # It's a windows path, ensure separator
            if not raw_path.endswith(os.sep):
                raw_backup_folder = Path(raw_path).resolve()
        else:
            raw_backup_folder = Path(raw_path).resolve()

        # FIX: SQL Server cannot write to User Profile (OneDrive, etc).
        # If path is in Users, fallback to C:\DB Backups
        if "Users" in str(raw_backup_folder):
            # FIX: Ensure C:\ (with slash) not just C:
            sys_drive = os.environ.get("SystemDrive", "C:")
            if not sys_drive.endswith("\\"):
                sys_drive += "\\"
            fallback_folder = Path(sys_drive) / "DB Backups"

            self._log_output(
                f"[!] Access Warning: SQL Server cannot write to '{raw_backup_folder}'"
            )
            self._log_output(f"[!] Switching to safe public path: '{fallback_folder}'")
            backup_folder = fallback_folder
        else:
            backup_folder = raw_backup_folder

        temp_dir = backup_folder / "Temp"

        # 2. Setup: Create directories
        try:
            # Ensure main folder exists
            backup_folder.mkdir(parents=True, exist_ok=True)

            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            self._log_output("[*] Created temporary backup directory")
            result.add_message(f"Backup directory: {temp_dir}")
        except Exception as e:
            result.add_error(f"Failed to create temp directory: {e}")
            result.finalize(OperationStatus.FAILED)
            return result

        # 3. Database Operations: Shrink -> Backup -> Verify
        # Only process requested DBs
        backup_results = []
        valid_bak_files = []

        if not selected_dbs:
            result.add_warning("No databases selected for backup.")

        for db in selected_dbs:
            self._log_output(f"[*] Processing Database: {db}")

            # A. Shrink (Best Effort)
            self._log_output("    - Shrinking...")
            shrink_success = self.shrink_database(db)
            if shrink_success:
                result.add_message(f"    - Shrunk: {db}")
            else:
                result.add_warning(f"    - Shrink failed: {db}")

            # B. Backup (Critical)
            backup_path = temp_dir / f"{db}_{timestamp}.bak"
            self._log_output(f"    - Backing up to: {backup_path.name}")
            backup_success = self.backup_database(db, str(backup_path))

            # C. Verify File Existence & Size
            file_verified = backup_path.exists() and backup_path.stat().st_size > 0

            if backup_success and file_verified:
                size_mb = backup_path.stat().st_size / (1024 * 1024)
                self._log_output(f"    - SUCCESS: {db} ({size_mb:.2f} MB)")
                valid_bak_files.append(backup_path)
                backup_results.append(True)

                result.add_resource(
                    Resource(
                        type=ResourceType.DATABASE,
                        name=db,
                        path=str(backup_path),
                        additional_info={"size_bytes": backup_path.stat().st_size},
                    )
                )
            else:
                self._log_output(f"    - FAILED: {db}", is_error=True)
                result.add_error(f"Backup failed for {db}")
                backup_results.append(False)

        # 4. AppSettings Operations: Copy
        self._log_output("[*] Processing AppSettings...")
        appsettings = self.config.get("appsettings_files")
        appsettings_results = []

        # Only process selected AppSettings
        if not selected_appsettings:
            result.add_warning("No AppSettings selected for backup.")

        for item in appsettings:
            if item["name"] not in selected_appsettings:
                continue

            copy_success = self.copy_appsettings(
                item["path"], item["name"], timestamp, str(temp_dir)
            )
            if copy_success:
                appsettings_results.append(True)
                result.add_message(f"    - Copied: {item['name']}")
            else:
                appsettings_results.append(False)
                result.add_warning(f"    - Failed to copy: {item['name']}")

        # 5. Zip Creation (Only if we have content)
        # 5. Zip Creation (Only if we have content)
        client_name = self.config.get("client_name", "UPC")
        branch_code = self.config.get("branch_code", "")
        pos_number = self.config.get("pos_number", "")

        # Validation: Branch Code and POS Number are mandatory for the new naming convention
        if not branch_code:
            result.add_error(
                "Invalid Configuration: Branch Code is required for backup."
            )
            result.finalize(OperationStatus.FAILED)
            return result

        if not pos_number:
            result.add_error(
                "Invalid Configuration: POS Number is required for backup."
            )
            result.finalize(OperationStatus.FAILED)
            return result

        # New Format: <clientName>_<BranchCode>_POS_<PosNumber>_<RmsBranchSrv>_DB_Backup_<DateTimeStamp>.zip
        # Note: <RmsBranchSrv> seems to imply the database name, but the spec says hardcoded textual logic or dynamic?
        # Example: UPC_1023_POS_01_RmsBranchSrv_DB_Backup_2026-01-28.zip
        # It's safest to include "RmsBranchSrv" as a literal string or strictly one of the primary DBs.
        # Given the instruction "RmsBranchSrv" in the format, I will use "RmsBranchSrv" as a fixed part of the name
        # OR if it's dynamic based on what's backed up, it creates ambiguity if multiple DBs.
        # The prompt Example: UPC_1023_POS_01_RmsBranchSrv_DB_Backup_... implies it might be the main DB context.
        # I'll use "RmsBranchSrv" literal to match the example exactly, as typically these backups are for the branch server.

        # Ensure date format is file-system safe (already handled by timestamp)
        # Re-formatting timestamp to match example: 2026-01-28_14-35-12
        # Current timestamp format: %d-%m-%Y_%I-%M-%S-%p (e.g. 28-01-2026_02-35-12-PM)
        # Request Example: 2026-01-28_14-35-12 (YYYY-MM-DD_HH-MM-SS)

        new_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        zip_name = f"{client_name}_{branch_code}_POS_{pos_number}_RmsBranchSrv_DB_Backup_{new_timestamp}.zip"
        zip_file = Path(backup_folder) / zip_name

        # Check if we have anything to zip
        if not valid_bak_files and not appsettings_results:
            result.add_error("No files successfully generated to backup.")
            result.finalize(OperationStatus.FAILED)
            return result

        self._log_output(f"[*] Creating Archive: {zip_file.name}")
        zip_success = False

        try:
            import zipfile

            with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add all files in temp_dir
                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file():
                        zipf.write(file_path, file_path.relative_to(temp_dir))

            # Verify Zip
            if zip_file.exists() and zip_file.stat().st_size > 0:
                zip_success = True
                self._log_output(
                    f"[✔] Archive Created Successfully ({zip_file.stat().st_size / 1024:.2f} KB)"
                )
                result.add_resource(
                    Resource(
                        type=ResourceType.FILE, name=zip_file.name, path=str(zip_file)
                    )
                )
            else:
                result.add_error("Zip file creation failed (empty or missing).")

        except Exception as e:
            error_msg = f"Zip creation crashed: {e}"
            self._log_output(error_msg, is_error=True)
            result.add_error(error_msg)

        # 6. Cleanup
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Non-critical

        # 7. Final Status Determination
        # Success = Zip exists AND All requested DBs backed up
        all_dbs_ok = all(backup_results) if selected_dbs else True

        if zip_success and all_dbs_ok:
            result.finalize(OperationStatus.SUCCESS)
            if os.name == "nt":
                try:
                    os.startfile(backup_folder)
                except Exception:
                    pass
        elif zip_success:
            result.finalize(OperationStatus.PARTIAL_SUCCESS)
            result.add_warning("Backup archive created but some databases failed.")
        else:
            result.finalize(OperationStatus.FAILED)
            result.add_error("Backup operation failed to produce an archive.")

        result.context["zip_file"] = str(zip_file)
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
            self._log_output(
                f"RESTORE FILELISTONLY failed for {backup_path}: {stderr}",
                is_error=True,
            )
            return "", ""

        logical_data = ""
        logical_log = ""

        lines = stdout.strip().split("\n")
        for line in lines:
            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    logical_name = parts[0].strip()
                    # With -s "|" and headers off, RESTORE FILELISTONLY format can vary
                    # but typically Column 1 is Name and Column 3 (index 2) is Type
                    # We check field 3 for 'D' (Data) or 'L' (Log)
                    if len(parts) >= 3:
                        file_type = parts[2].strip()
                        if file_type == "D" and not logical_data:
                            logical_data = logical_name
                        elif file_type == "L" and not logical_log:
                            logical_log = logical_name

        if not logical_data or not logical_log:
            self._log_output(
                f"Could not parse logical names from output: {stdout}", is_error=False
            )

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

    # ===== SERVICE CONTROL =====

    def control_service(self, service_name: str, action: str) -> bool:
        """Control Windows service (start/stop/restart)"""
        action = action.lower()

        if action == "restart":
            self._log_output(f"Restarting service: {service_name}...")
            stop_ok = self.control_service(service_name, "stop")
            time.sleep(2)  # Brief pause
            start_ok = self.control_service(service_name, "start")
            return stop_ok and start_ok

        cmd = []
        if action == "start":
            cmd = ["net", "start", service_name]
        elif action == "stop":
            cmd = ["net", "stop", service_name]
        else:
            return False

        code, _, stderr = self.run_command(cmd, timeout=self.SERVICE_TIMEOUT)

        if code == 0:
            self._log_output(f"Service {action} successful: {service_name}")
            return True

        # Check if already started/stopped
        if "started" in stderr.lower() or "started" in stderr.lower():
            self._log_output(f"Service state OK: {service_name}")
            return True

        self._log_output(f"Service {action} failed: {stderr}", is_error=True)
        return False
