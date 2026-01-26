"""
Configuration management for persisting user settings with encryption
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any
import logging

from app.models.settings import AppSettings
from app.logic.crypto import CryptoManager, ConfigMigrator

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration persistence with encryption"""

    def __init__(self):
        self.config_dir = Path.home() / ".pos_admin_tool"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)

        self.crypto = CryptoManager()
        self.migrator = ConfigMigrator(self.config_file)
        self.settings = AppSettings()

    def load(self) -> AppSettings:
        """Load configuration from file with migration and validation"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)

                # Validate schema
                if not self.migrator.validate_schema(data):
                    logger.warning("Config schema invalid, attempting repair")
                    data = self.migrator.repair_config(data)

                # Migrate if needed (plaintext → encrypted)
                if self.migrator.needs_migration(data):
                    logger.info("Migrating config from plaintext to encrypted format")
                    data = self.migrator.migrate(data)
                    # Save migrated config immediately
                    with open(self.config_file, "w") as f:
                        json.dump(data, f, indent=2)

                # Decrypt sensitive fields
                data = self.crypto.decrypt_dict(data)

                # Create settings object
                self.settings = AppSettings(**data)

                # If password decryption failed, log warning
                if not self.settings.sql_password:
                    logger.warning(
                        "SQL password could not be decrypted. User will need to re-enter."
                    )

            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Error loading config: {e}")
                # Create backup of corrupted config
                backup_file = self.config_file.with_suffix(".corrupted.json")
                try:
                    import shutil

                    shutil.copy2(self.config_file, backup_file)
                    logger.info(f"Backed up corrupted config to {backup_file}")
                except Exception as backup_error:
                    logger.error(f"Failed to backup corrupted config: {backup_error}")

                # Create default config
                self.settings = AppSettings()
                self.save()
            except Exception as e:
                logger.error(f"Unexpected error loading config: {e}")
                self.settings = AppSettings()
        else:
            # Create default config
            self.settings = AppSettings()
            self.save()

        return self.settings

    def save(self):
        """Save configuration to file with encryption"""
        try:
            # Convert settings to dict
            data = asdict(self.settings)

            # Encrypt sensitive fields
            data = self.crypto.encrypt_dict(data)

            # Write to file
            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info("Configuration saved successfully")

        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise

    def update(self, **kwargs):
        """Update specific settings"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                # Special handling for password
                if key == "sql_password" and value:
                    # Only update if non-empty
                    setattr(self.settings, key, value)
                elif key != "sql_password":
                    setattr(self.settings, key, value)
        self.save()

    def get(self, key: str, default=None):
        """Get a specific setting"""
        return getattr(self.settings, key, default)

    def validate_credentials(self) -> bool:
        """Validate that SQL credentials are available"""
        return bool(self.settings.sql_password)

    def get_sql_connection_info(self) -> Dict[str, str]:
        """Get SQL connection info with safe logging"""
        return {
            "instance": self.settings.sql_instance,
            "user": self.settings.sql_user,
            "password": "***" if self.settings.sql_password else "MISSING",
        }
