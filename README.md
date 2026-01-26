# POS Admin Tool

A modern Python desktop application that replaces the existing batch files for managing POS (Point of Sale) systems.

## Features

- **Service Management**: Monitor and control Windows services (RMS.CashierService, RMS.BranchService, RMSServiceManager)
- **Database Operations**: Backup, restore, and shrink SQL Server databases
- **Cleanup Operations**: Delete services, databases, folders, and registry entries
- **Modern GUI**: User-friendly interface with real-time status updates
- **Configuration Persistence**: Saves all settings between sessions

## Requirements

- Windows 10/11
- Python 3.8 or higher
- SQL Server (with sqlcmd available in PATH)
- Administrator privileges

## Installation

### From Source

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt