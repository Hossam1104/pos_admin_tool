"""
Executes batch-equivalent commands with proper error handling
"""

import subprocess
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import shutil
import winreg
from app.utils.logger import get_logger

logger = get_logger()


class BatchRunner:
    """Executes commands equivalent to the original batch files"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.output_callback = None

    def set_output_callback(self, callback):
        """Set callback for real-time output"""
        self.output_callback = callback

    def _log_output(self, message: str, is_error: bool = False):
        """Log output and send to callback"""
        logger.info(message) if not is_error else logger.error(message)
        if self.output_callback:
            self.output_callback(message, is_error)

    def run_command(
        self, command: List[str], shell: bool = False
    ) -> Tuple[int, str, str]:
        """Execute a command and return results"""
        try:
            self._log_output(f"Executing: {' '.join(command)}")
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.stdout:
                self._log_output(result.stdout)
            if result.stderr:
                self._log_output(result.stderr, is_error=True)

            return result.returncode, result.stdout, result.stderr

        except Exception as e:
            error_msg = f"Command execution failed: {e}"
            self._log_output(error_msg, is_error=True)
            return 1, "", error_msg

    def sqlcmd(self, query: str, database: str = "master") -> Tuple[int, str, str]:
        """Execute SQL query using sqlcmd"""
        sql_instance = self.config.get("sql_instance")
        sql_user = self.config.get("sql_user")
        sql_password = self.config.get("sql_password")

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

        return self.run_command(cmd)

    # ===== CLEANUP OPERATIONS =====

    def stop_service(self, service_name: str) -> bool:
        """Stop a Windows service"""
        self._log_output(f"[*] Stopping service: {service_name}")
        returncode, stdout, stderr = self.run_command(["net", "stop", service_name])
        return returncode == 0 or returncode == 2  # 2 = service not running

    def delete_service(self, service_name: str) -> bool:
        """Delete a Windows service"""
        self._log_output(f"[*] Deleting service: {service_name}")
        returncode, stdout, stderr = self.run_command(["sc", "delete", service_name])
        return returncode == 0

    def drop_database(self, database_name: str) -> bool:
        """Drop a SQL Server database"""
        self._log_output(f"[*] Dropping database: {database_name}")
        returncode, stdout, stderr = self.sqlcmd(
            f"DROP DATABASE IF EXISTS [{database_name}]"
        )
        return returncode == 0

    def delete_folder(self, folder_path: str) -> bool:
        """Delete a folder recursively"""
        folder = Path(folder_path)
        if not folder.exists():
            return True

        try:
            self._log_output(f"[*] Deleting folder: {folder}")
            shutil.rmtree(folder)
            return True
        except Exception as e:
            self._log_output(f"Failed to delete folder {folder}: {e}", is_error=True)
            return False

    def cleanup_registry(self) -> bool:
        """Clean registry uninstall entries and RMS_ folders"""
        self._log_output("[*] Cleaning registry uninstall entries and RMS_ folders...")

        try:
            # PowerShell command equivalent to batch file
            ps_script = """
            $uninstallKey = 'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall'
            Get-ChildItem -Path $uninstallKey | ForEach-Object {
                $name = $_.PSChildName
                if ($name -like 'RMS_*') {
                    Write-Host "Deleting uninstall key: $name"
                    Remove-Item -Path ('{0}\\{1}' -f $uninstallKey, $name) -Recurse -Force -ErrorAction SilentlyContinue
                    $folder = Join-Path 'C:\\ProgramData' $name
                    if (Test-Path $folder) { 
                        Remove-Item $folder -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
            }
            """

            cmd = ["powershell", "-nologo", "-noprofile", "-Command", ps_script]
            returncode, stdout, stderr = self.run_command(cmd)

            if stdout:
                self._log_output(stdout)
            if stderr and "ErrorAction" not in stderr:
                self._log_output(stderr, is_error=True)

            return returncode == 0

        except Exception as e:
            self._log_output(f"Registry cleanup failed: {e}", is_error=True)
            return False

    def execute_cleanup(self) -> bool:
        """Execute the complete cleanup operation (equivalent to POS_CleanupAndDelete.bat)"""
        self._log_output("Starting cleanup operation...")

        # Stop and delete services
        services = self.config.get("services")
        for service in services:
            self.stop_service(service)
            self.delete_service(service)

        # Drop databases
        databases = self.config.get("databases")
        for db in databases:
            self.drop_database(db)

        # Delete folders
        folders = self.config.get("folders_to_delete")
        for folder in folders:
            self.delete_folder(folder)

        # Clean registry
        self.cleanup_registry()

        self._log_output("[✔] Cleanup and deletion complete.")
        return True

    # ===== RESTORE OPERATIONS =====

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

    def execute_restore(
        self, client_name: str, db_choice: str, backup_path: str
    ) -> bool:
        """Execute database restore operation"""
        # Determine target database
        if db_choice == "1":
            base_db = "RmsBranchSrv"
        else:
            base_db = "RmsCashierSrv"

        target_db = f"{client_name}_{base_db}"

        self._log_output(f"Starting restore operation for: {target_db}")
        self._log_output(f"Backup file: {backup_path}")

        # Get SQL paths
        data_path, log_path = self.get_sql_paths()
        if not data_path or not log_path:
            self._log_output("[ERROR] Cannot determine DATA/LOG paths.", is_error=True)
            return False

        # Get logical file names
        logical_data, logical_log = self.get_backup_filelist(backup_path)
        if not logical_data or not logical_log:
            self._log_output(
                "[ERROR] Could not read logical files from backup.", is_error=True
            )
            return False

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
            self._log_output("[WARN] Failed to drop existing database", is_error=True)

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
            self._log_output(f"===== SUCCESS =====")
            self._log_output(f"DB: [{target_db}]")
            self._log_output(f"MDF: {target_mdf}")
            self._log_output(f"LDF: {target_ldf}")
            return True
        else:
            self._log_output("[ERROR] Restore failed", is_error=True)
            return False

    # ===== BACKUP OPERATIONS =====

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

    def execute_backup(self) -> Tuple[bool, str]:
        """Execute shrink and backup operation"""
        timestamp = datetime.now().strftime("%d-%m-%Y_%I-%M-%S-%p")
        backup_folder = self.config.get("backup_folder")
        temp_dir = Path(backup_folder) / "Temp"

        # Create directories
        temp_dir.mkdir(parents=True, exist_ok=True)

        self._log_output("[*] Creating temporary backup directory...")

        # Shrink and backup databases
        databases = self.config.get("databases")
        for db in databases:
            self._log_output(f"[*] Shrinking database: {db}")
            self.shrink_database(db)

            backup_path = temp_dir / f"{db}_{timestamp}.bak"
            self._log_output(f"[*] Backing up database: {db}")
            self.backup_database(db, str(backup_path))

        # Copy appsettings files
        self._log_output("[*] Copying and timestamping appsettings.json files...")
        appsettings = self.config.get("appsettings_files")
        for item in appsettings:
            self.copy_appsettings(item["path"], item["name"], timestamp, str(temp_dir))

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

            # Cleanup temp directory
            shutil.rmtree(temp_dir)

            self._log_output(f"[✔] Backup complete: {zip_file}")

            # Open backup folder
            if os.name == "nt":
                os.startfile(backup_folder)

            return True, str(zip_file)

        except Exception as e:
            self._log_output(f"Failed to create ZIP: {e}", is_error=True)
            return False, ""
