# RMS+ POS Admin Tool - Production v1.0

## 1️⃣ Project Overview

**The RMS+ POS Admin Tool** is a centralized, Windows-native utility designed for Digital Business Systems (DBS) to manage execution-critical operations for Point of Sale (POS) and Retail Management Systems (RMS) environments. It replaces legacy batch scripts with a robust, GUI-based Python application that enforces safety, validation, and visual feedback.

### Problem Solved
Legacy batch files lacked validation, error handling, and visibility. Operators could accidentally execute destructive operations or fail to notice silent failures in backups. This tool introduces:
- **Strict Validation**: Prevents operations on invalid paths or databases.
- **Visual Feedback**: Real-time logging and status indicators (Red/Green) for services.
- **Safety**: "Danger Zone" operations require explicit confirmation.

### Target Environment
- **OS**: Windows 10/11 / Windows Server 2016+
- **Database**: Microsoft SQL Server (2014 or newer recommended)
- **Services**: Manages `RmsBranchSrv`, `RmsCashierSrv`, and related services.
- **Privileges**: Requires Administrator elevation.

---

## 📘 **Full Project Documentation (PDF)**
[POS_Admin_Tool_Documentation.pdf](./POS_Admin_Tool_Documentation.pdf)  
*Refer to this document for detailed architectural diagrams, screen-by-screen workflows, and disaster recovery protocols.*

---

## 2️⃣ Key Features

### Service Management
- **Live Monitoring**: innovative, real-time status checking of `RMS*` and `POS*` Windows services.
- **Control**: Start, Stop, and Restart services with one click.
- **Visual Safety**: Icons (`✓`/`⏹`) and color-coding (Green/Red) indicate instant status.

### Database Backup / Restore
- **Selective Backup**: Choose specific targeted databases or app setting files.
- **Automated Naming**: Backups follow a strict `[Client]_[Type]_[Timestamp].bak` naming convention.
- **Advanced Restore**:
    - Supports custom MDF/LDF path targeting.
    - Handles `WITH MOVE` logic automatically to prevent file collisions.
    - **Critical Safety**: Prevents restoring over active databases without explicit confirmation.

### Cleanup Operations (Danger Zone)
- **Automated Maintenance**: Clears temporary cache, log files, and resets service states.
- **Safety Lock**: Requires explicit confirmation dialogs to execute.

### Configuration Persistence
- **JSON-based Settings**: Persists paths (`mdf_path`, `ldf_path`, `backup_path`) between sessions.
- **Auto-Discovery**: Automatically detects available SQL instances and databases on specific networks.

---

## 3️⃣ Architecture Overview

The application follows a **Model-View-Controller (MVC)** pattern to ensure separation of concerns and thread safety.

```ascii
[ UI Layer (View) ] <---> [ MainController ] <---> [ Logic Layer (BatchRunner) ]
       |                          |                        |
[ ServiceMonitor ]        [ Config Manager ]       [ System / SQLCMD ]
       |                                                   |
[ Windows SCM ]                                     [ SQL Server ]
```

- **UI Layer (`app/ui.py`)**: Handles user interaction, rendering, and input validation. **No business logic resides here.**
- **Controller**: Orchestrates requests, manages background threads (`WorkerThread`), and routes logging.
- **Logic Layer (`app/logic.py`)**: Executes the heavy lifting (SQLCMD, PowerShell, File I/O). It is decoupled from the UI to allow for headless testing if needed.
- **Service Layer (`app/services.py`)**: Dedicated monitor loop that uses `subprocess` (with window suppression) to query `sc.exe` status without freezing the UI.

---

## 4️⃣ Project Structure

```text
pos_admin_tool/
├── app/
│   ├── ui.py               # Main Window, Panels, and Widget definitions
│   ├── logic.py            # Core Business Logic (Backup, Restore, Cleanup)
│   ├── services.py         # Windows Service Monitoring (Threaded)
│   ├── config.py           # Configuration Management (JSON persistence)
│   ├── admin.py            # UAC Elevation handling
│   ├── logger.py           # Centralized logging configuration
│   └── models/
│       ├── operation.py    # Data classes for Operation Results
│       └── settings.py     # Data classes for App Settings
├── assets/
│   └── icons/              # Application icons
├── config/                 # Generated configuration files
├── build_exe.bat           # Build automation script
├── setup.py                # PyInstaller build configuration
└── main.py                 # Application Entry Point
```

---

## 5️⃣ Installation & Setup

### Prerequisites
- **OS**: Windows 10/11 or Windows Server.
- **Python**: Python 3.10 or newer.
- **SQL Server**: Local or accessible SQL Server instance with `sqlcmd` utility in PATH.

### Dependencies
Install the required packages:
```powershell
pip install PySide6 pywin32
```

### Admin Privileges
The application performs system-level operations (Service Control, File Access in Protected Dirs).
**It must be run as Administrator.**

---

## 6️⃣ Running the Application

### From Source
1. Open PowerShell as Administrator.
2. Navigate to the project root.
3. Run:
   ```powershell
   python app/main.py
   ```
4. On first launch, `config/settings.json` will be generated with defaults.

---

## 7️⃣ Building the Executable

The project uses **PyInstaller** to create a standalone, distribution-ready `.exe`.

1. Run the build script:
   ```powershell
   build_exe.bat
   ```
   *Alternatively: `python setup.py`*

2. **Output**: The executable will be generated in `dist/RMSPlus_POSAdmin_v1.0.exe`.

**Note:**
- The build process automatically suppresses console windows for background tasks.
- Ensure your Antivirus does not block the new executable (common with unsigned PyInstaller builds).

---

## 8️⃣ Usage Guide

### Configuration Panel
1. Enter your **SQL Server Name** (e.g., `.\MSSQLSERVER`).
2. Set your **MDF/LDF Paths** (Defaults to `D:\DB Backups`).
3. Set your **Backup Path**.
4. Click **Test Connection** to verify SQL connectivity and auto-populate the database list.
5. Click **Save Configuration**.

### Service Control
- View the real-time status of RMS/POS services.
- Click **Stop** / **Start** to manage them.
- *Note: Backup/Restore operations may require services to be stopped first.*

### Restore Workflow
1. Go to the **Restore** section.
2. Select the **Target Database Type** (Branch or Cashier).
3. Browse for the `.bak` file.
4. (Optional) Adjust the **MDF/LDF** destination paths if you need to move data files.
5. Click **RESTORE DATABASE**.

### Danger Zone (Cleanup)
- Located at the bottom of the UI.
- **Action**: Stops services, clears temp files, releases file locks.
- **Use Case**: Recovering from a stuck state or preparing for a clean install.

---

## 9️⃣ Standard Operating Procedure (How to Use)

### Daily Operations
- **Morning Check**: Launch the tool and ensure `RmsBranchSrv` and `RmsCashierSrv` are marked as **Running** (Green).
- **Service Restart**: If a POS terminal is not syncing, use the **Restart** button in the Service Control panel before escalating to IT.

### Database Maintenance
1. **Backup**: Always perform a backup before any manual SQL intervention. Go to the **Backup** panel, select the DB, and click **Run**.
2. **Restore (Emergency Only)**: 
   - Stop services first.
   - Select the `.bak` file.
   - Verify the **Client Name** matches the store code.
   - Execute the restore and wait for the success prompt.

### System Reset
- Use the **Danger Zone** ONLY if the application is completely stuck. Type `CONFIRM DANGER ZONE` to unlock the button. This will force-stop all RMS components.


---

## 9️⃣ Safety & Warnings

### ⚠️ Destructive Operations
- **Restore**: Overwrites the existing target database. **This cannot be undone.** Always ensure a backup exists before restoring.
- **Cleanup**: Deletes temporary files and force-stops services. Usage during active business hours may disrupt operations.

### Recommendations
1. **Always Backup** before attempting a Restore.
2. Verify **SQL Permissions** (the user running the tool must have `sysadmin` or `dbcreator` roles).
3. Do not assume "Success" means data integrity—verify the application loads after restore.

---

🔟 Logging & Troubleshooting

### Log Location
- **UI Log**: Visible in the black console panel at the bottom of the interface.
- **File Log**: Stored in `logs/` directory (created automatically).

### Common Issues
| Issue | Resolution |
|-------|------------|
| **Access Denied** | Ensure you are running as Administrator. |
| **SQL Connection Failed** | Check firewall, TCP/IP enablement, and correct Instance Name. |
| **Console Flickering** | Update to v1.1. Subprocess window suppression was added in this version. |
| **Restore Failed (In Use)** | Ensure no other applications (SSMS, ERP) are connected to the DB. |

---

## 1️⃣1️⃣ Full Documentation (PDF)

[POS_Admin_Tool_Documentation.pdf](./POS_Admin_Tool_Documentation.pdf)

Please consult the PDF for:
- Detailed Database Schema flow
- Network Topology diagrams
- Comprehensive Disaster Recovery scenarios

---

## 1️⃣2️⃣ License

See `LICENSE` file for details.