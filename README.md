# DBS POS Admin Tool (RMS+)

**Version:** 1.0 (Production)  
**Provider:** Digital Business Systems (DBS)  
**Client:** AlDawaa Medical Service Company

---

## 📖 Introduction

The **POS Admin Tool** is your central control panel for managing the RMS+ Point of Sale system. It allows authorized store managers and IT support staff to:
- **Monitor** real-time status of POS services.
- **Backup** databases before operations.
- **Restore** data in emergencies.
- **Reset** stuck systems safely.
- **Verify** branch installation status.

> **⚠️ Requirement:** This application must always be run as **Administrator**.

---

## 🚀 Quick Start Guide

### 1. Launching the App
Double-click the `RMSPlus_POSAdmin_v1.0.exe` icon. The application will automatically request Administrator privileges.

### 2. Dashboard Overview
Upon launch, you will see the **Dashboard**:
- **Main Server Status**: Traffic light indicator (Green = Connected, Red = Offline).
- **Environment Badge**: Shows if the system is in `PRODUCTION` or `TESTING` mode.
- **Service Status**: Quick view of whether your POS services are running.

---

## 🛠️ How to Use

### 1. Configuration & Verification
Before running operations, ensure the tool is connected to the right system.
1. Go to the **Configuration** tab.
2. Check the **Branch Code** (e.g., `P001`) and **POS Number**.
3. Click the **"Verify Branch"** button.
   - **Success**: Confirms this branch is registered on the Main Server.
   - **Failure**: Checks if the Branch Code is incorrect or the server is unreachable.
4. Click **Test Connection** to ensure SQL Database connectivity.

### 2. Managing Services (Start/Stop)
If a POS terminal is offline or not syncing:
1. Go to **Service Control**.
2. Look for **RmsBranchSrv** or **RmsCashierSrv**.
3. Click **Restart**.
   - The status light will cycle from Green -> Red -> Green.

### 3. Backup (Safety First)
**Always run a backup before making changes.**
1. Go to the **Backup** tab.
2. Select the databases you want to save (usually pre-selected).
3. Click **Run Backup**.
   - A success message will appear when finished.

### 4. Restore (Emergency Only)
**⚠️ Caution:** This overwrites current data.
1. Go to the **Restore** tab.
2. Select the **Target Database** (e.g., `Branch` or `Cashier`).
3. Browse for your `.bak` backup file.
4. Click **Restore Database**.

### 5. Danger Zone (Advanced)
Use this section only if the system is completely stuck or needs to be uninstalled.
- **Cleanup System**: Force-stops services and deletes temporary files.
- **Uninstall Options**:
  - **Uninstall Branch**: Deregisters the branch from the server.
  - **Uninstall POS**: Deregisters the specific POS machine.
  - *Note: These require you to check "I understand the risks" and confirm multiple prompts.*

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Access Denied"** | Close the app and Right-Click -> **Run as Administrator**. |
| **"SQL Connection Failed"** | Check if the SQL Server service is running in Windows Services. |
| **"Verify Branch" Failed** | Ensure the **Main Server Status** is Green. Check internet connection. |
| **App won't open** | Restart the computer and try again. |

---

## 📞 Support
For critical issues, please contact **DBS Support**.

*© 2026 Digital Business Systems*