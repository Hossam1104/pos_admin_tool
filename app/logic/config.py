"""
Configuration management for persisting user settings
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any
from app.models.settings import AppSettings


class ConfigManager:
    """Manages application configuration persistence"""

    def __init__(self):
        self.config_dir = Path.home() / ".pos_admin_tool"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        self.settings = AppSettings()

    def load(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self.settings = AppSettings(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading config: {e}")
                # Create default config
                self.save()
        return self.settings

    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(asdict(self.settings), f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def update(self, **kwargs):
        """Update specific settings"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()

    def get(self, key: str, default=None):
        """Get a specific setting"""
        return getattr(self.settings, key, default)
