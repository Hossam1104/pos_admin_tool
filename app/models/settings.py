"""
Data models for application settings
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class AppSettings:
    """Application settings model"""

    # SQL Configuration
    sql_instance: str = "."
    sql_user: str = "sa"
    sql_password: str = "P@ssw0rd"

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

    # Folders to delete
    folders_to_delete: List[str] = field(
        default_factory=lambda: [
            r"C:\Workspaces",
            r"C:\ProgramData\Logs",
            r"C:\ProgramData\Cashier",
            r"C:\ProgramData\Branch",
            r"C:\ProgramData\DBS",
            r"C:\ProgramData\RMS_Plus",
            r"C:\ProgramData\RMS_Plus_Downloads",
            r"C:\ProgramData\RMS_Plus_ReleaseRepo",
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
    client_name: str = ""

    # Last used backup directory
    last_backup_dir: str = ""
