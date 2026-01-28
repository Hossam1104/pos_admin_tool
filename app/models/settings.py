"""
Data models for application settings
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import os
from pathlib import Path


@dataclass
class AppSettings:
    """Application settings model"""

    # SQL Configuration
    sql_instance: str = "."
    sql_user: str = "sa"
    sql_password: Optional[str] = None  # Will be encrypted

    # Databases
    databases: List[str] = field(
        default_factory=lambda: ["RmsCashierSrv", "RmsBranchSrv"]
    )

    # Services
    services: List[str] = field(
        default_factory=lambda: [
            "RMS.CashierService",
            "RMS.BranchService",
            "RMSServiceManager",
        ]
    )

    known_services: List[str] = field(
        default_factory=lambda: [
            "RMS.CashierService",
            "RMS.BranchService",
            "RMSServiceManager",
        ]
    )

    # Folders to delete
    folders_to_delete: List[str] = field(
        default_factory=lambda: [
            r"C:\Workspaces",
            str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Logs"),
            str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Cashier"),
            str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Branch"),
            str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "DBS"),
            str(Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "RMS_Plus"),
            str(
                Path(os.environ.get("ProgramData", r"C:\ProgramData"))
                / "RMS_Plus_Downloads"
            ),
            str(
                Path(os.environ.get("ProgramData", r"C:\ProgramData"))
                / "RMS_Plus_ReleaseRepo"
            ),
        ]
    )

    # Backup configuration
    backup_folder: str = r"D:\DB Backups"

    # AppSettings files
    appsettings_files: List[Dict[str, str]] = field(
        default_factory=lambda: [
            {
                "path": r"C:\Workspaces\DBS\RMS\RMS.BranchServer\appsettings.json",
                "name": "RMS_BranchService_appsettings.json",
            },
            {
                "path": r"C:\Workspaces\DBS\RMS\RMS.CashierServer\appsettings.json",
                "name": "RMS_CashierGRPCService_appsettings.json",
            },
            {
                "path": r"C:\Workspaces\DBS\RMS\RMS.CashierUI\appsettings.json",
                "name": "RMS_CashierUIService_appsettings.json",
            },
        ]
    )

    # Client name (for restore)
    client_name: str = "UPC"

    # Last used backup directory
    last_backup_dir: str = ""

    # Restore Preferences (Persisted)
    mdf_path: Optional[str] = None
    ldf_path: Optional[str] = None

    # New Configuration Fields
    branch_code: str = ""
    pos_number: str = ""
    # Path Configuration (Standardized)
    release_path: str = r"C:\ProgramData\RMS_Plus\ReleaseNumber.txt"
    env_config_path: str = r"C:\Workspaces\DBS\RMS\RMS.CashierServer\appsettings.json"
