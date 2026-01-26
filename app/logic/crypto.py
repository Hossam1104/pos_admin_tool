"""
Secure credential management using Windows DPAPI
"""

import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

try:
    import win32crypt
    import win32cryptcon

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("win32crypt not available, using base64 fallback (not secure)")


@dataclass
class EncryptedData:
    """Container for encrypted credential data"""

    data: str  # Base64 encoded encrypted data
    version: int = 1
    encryption_method: str = "DPAPI" if CRYPTO_AVAILABLE else "BASE64"


class CryptoManager:
    """Manages secure credential storage using Windows DPAPI"""

    def __init__(self, entropy: Optional[str] = None):
        """
        Initialize crypto manager

        Args:
            entropy: Optional entropy string for additional security
        """
        self.entropy = entropy.encode("utf-8") if entropy else None

    def encrypt(self, plaintext: str) -> Optional[EncryptedData]:
        """
        Encrypt plaintext using DPAPI or fallback

        Args:
            plaintext: Text to encrypt

        Returns:
            EncryptedData or None if encryption fails
        """
        if not plaintext:
            return None

        try:
            if CRYPTO_AVAILABLE:
                # Use Windows DPAPI
                encrypted = win32crypt.CryptProtectData(
                    plaintext.encode("utf-8"),
                    "POSAdminTool",
                    self.entropy,
                    None,
                    None,
                    win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN,
                )
                encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")
                return EncryptedData(data=encrypted_b64, encryption_method="DPAPI")
            else:
                # Fallback to base64 (not secure, for development only)
                logger.warning(
                    "Using base64 fallback encryption - NOT SECURE FOR PRODUCTION"
                )
                encrypted_b64 = base64.b64encode(plaintext.encode("utf-8")).decode(
                    "utf-8"
                )
                return EncryptedData(data=encrypted_b64, encryption_method="BASE64")

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return None

    def decrypt(self, encrypted_data: EncryptedData) -> Optional[str]:
        """
        Decrypt encrypted data

        Args:
            encrypted_data: EncryptedData instance

        Returns:
            Decrypted plaintext or None if decryption fails
        """
        if not encrypted_data or not encrypted_data.data:
            return None

        try:
            encrypted_bytes = base64.b64decode(encrypted_data.data)

            if encrypted_data.encryption_method == "DPAPI" and CRYPTO_AVAILABLE:
                # Use Windows DPAPI
                decrypted = win32crypt.CryptUnprotectData(
                    encrypted_bytes,
                    self.entropy,
                    None,
                    None,
                    win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN,
                )
                return decrypted[1].decode("utf-8")
            elif encrypted_data.encryption_method == "BASE64":
                # Fallback base64 decoding
                return base64.b64decode(encrypted_data.data).decode("utf-8")
            else:
                logger.error(
                    f"Unknown encryption method: {encrypted_data.encryption_method}"
                )
                return None

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt specific sensitive fields in a dictionary"""
        encrypted = data.copy()

        # Fields to encrypt
        sensitive_fields = ["sql_password"]

        for field in sensitive_fields:
            if field in encrypted and encrypted[field]:
                encrypted_data = self.encrypt(encrypted[field])
                if encrypted_data:
                    # Store as JSON-serializable dict
                    encrypted[field] = asdict(encrypted_data)
                else:
                    # If encryption fails, remove the field for safety
                    del encrypted[field]

        return encrypted

    def decrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt specific sensitive fields in a dictionary"""
        decrypted = data.copy()

        # Fields that might be encrypted
        sensitive_fields = ["sql_password"]

        for field in sensitive_fields:
            if field in decrypted and isinstance(decrypted[field], dict):
                try:
                    encrypted_data = EncryptedData(**decrypted[field])
                    plaintext = self.decrypt(encrypted_data)
                    if plaintext:
                        decrypted[field] = plaintext
                    else:
                        # If decryption fails, keep encrypted version
                        # UI will prompt user to re-enter
                        logger.warning(f"Failed to decrypt {field}, keeping encrypted")
                except (TypeError, ValueError) as e:
                    logger.warning(f"Invalid encrypted data for {field}: {e}")
                    # If it's a string, might be plaintext (old format)
                    if isinstance(decrypted[field], str):
                        # This is plaintext from old config
                        logger.info(f"Found plaintext {field}, will encrypt on save")
                    else:
                        # Invalid format, remove
                        del decrypted[field]

        return decrypted


class ConfigMigrator:
    """Handles migration of configuration files"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.backup_path = config_path.with_suffix(".json.backup")
        self.crypto = CryptoManager()

    def needs_migration(self, config_data: Dict[str, Any]) -> bool:
        """Check if config needs migration from plaintext to encrypted"""
        if "sql_password" in config_data:
            # Check if password is plaintext (string) vs encrypted (dict)
            return isinstance(config_data["sql_password"], str)
        return False

    def migrate(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate plaintext config to encrypted format"""
        if not self.needs_migration(config_data):
            return config_data

        logger.info("Migrating plaintext credentials to encrypted format")

        # Create backup of original config
        try:
            with open(self.backup_path, "w") as f:
                json.dump(config_data, f, indent=2)
            logger.info(f"Created config backup at {self.backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")

        # Encrypt sensitive fields
        migrated = self.crypto.encrypt_dict(config_data)
        logger.info("Credentials encrypted successfully")

        return migrated

    def validate_schema(self, config_data: Dict[str, Any]) -> bool:
        """Validate config schema has required fields"""
        required_fields = [
            "sql_instance",
            "sql_user",
            "databases",
            "services",
            "folders_to_delete",
            "backup_folder",
        ]

        for field in required_fields:
            if field not in config_data:
                logger.error(f"Missing required field: {field}")
                return False

        return True

    def repair_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to repair corrupted configuration"""
        repaired = config_data.copy()

        # Ensure lists exist
        if "databases" not in repaired or not isinstance(repaired["databases"], list):
            repaired["databases"] = ["RmsCashierSrv", "RmsBranchSrv"]

        if "services" not in repaired or not isinstance(repaired["services"], list):
            repaired["services"] = [
                "RMS.CashierService",
                "RMS.BranchService",
                "RMSServiceManager",
            ]

        if "folders_to_delete" not in repaired or not isinstance(
            repaired["folders_to_delete"], list
        ):
            repaired["folders_to_delete"] = []

        # Ensure required string fields
        if "sql_instance" not in repaired or not repaired["sql_instance"]:
            repaired["sql_instance"] = "."

        if "sql_user" not in repaired or not repaired["sql_user"]:
            repaired["sql_user"] = "sa"

        if "backup_folder" not in repaired or not repaired["backup_folder"]:
            repaired["backup_folder"] = str(
                Path(os.environ.get("SystemDrive", "C:")) / "DB Backups"
            )

        return repaired
