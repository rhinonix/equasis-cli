#!/usr/bin/env python3
"""
Credential management following industry best practices
Supports XDG Base Directory Specification and standard credential hierarchy
"""

import os
import json
import getpass
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages Equasis credentials following industry best practices"""

    def __init__(self):
        self.app_name = "equasis-cli"
        self.config_dir = self._get_config_directory()
        self.credentials_file = self.config_dir / "credentials.json"

    def _get_config_directory(self) -> Path:
        """Get configuration directory following XDG Base Directory Specification"""
        # Follow XDG Base Directory Specification
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')

        if xdg_config_home:
            config_dir = Path(xdg_config_home) / self.app_name
        else:
            # Default to ~/.config/equasis-cli on Unix systems
            home = Path.home()
            if os.name == 'posix':  # Unix-like systems
                config_dir = home / '.config' / self.app_name
            else:  # Windows
                config_dir = home / '.equasis-cli'

        return config_dir

    def get_credentials(self, username_arg: Optional[str] = None,
                       password_arg: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Get credentials following industry-standard hierarchy:
        1. Command line arguments (highest priority)
        2. Environment variables
        3. Configuration file (lowest priority)

        Returns:
            Tuple of (username, password) or (None, None) if not found
        """
        username = None
        password = None

        # 1. Command line arguments (highest priority)
        if username_arg and password_arg:
            logger.debug("Using credentials from command line arguments")
            return username_arg, password_arg

        # 2. Environment variables
        env_username = os.environ.get('EQUASIS_USERNAME')
        env_password = os.environ.get('EQUASIS_PASSWORD')

        if env_username and env_password:
            logger.debug("Using credentials from environment variables")
            return env_username, env_password

        # 3. Configuration file
        config_username, config_password = self._load_from_config()
        logger.debug(f"Config file check: username={'set' if config_username else 'not set'}, password={'set' if config_password else 'not set'}")
        if config_username and config_password:
            logger.debug(f"Using credentials from config file: {self.credentials_file}")
            return config_username, config_password

        # Nothing found
        logger.debug("No credentials found in any source")
        return None, None

    def _load_from_config(self) -> Tuple[Optional[str], Optional[str]]:
        """Load credentials from configuration file"""
        if not self.credentials_file.exists():
            return None, None

        try:
            with open(self.credentials_file, 'r') as f:
                config = json.load(f)

            username = config.get('username')
            password = config.get('password')

            return username, password

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load credentials from {self.credentials_file}: {e}")
            return None, None

    def save_credentials(self, username: str, password: str) -> bool:
        """
        Save credentials to configuration file

        Args:
            username: Equasis username
            password: Equasis password

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Prepare credentials data
            credentials = {
                'username': username,
                'password': password,
                'created_by': 'equasis-cli',
                'note': 'Equasis credentials for maritime intelligence tool'
            }

            # Write credentials file
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)

            # Set secure permissions (owner read/write only)
            if os.name == 'posix':
                self.credentials_file.chmod(0o600)

            logger.info(f"Credentials saved to {self.credentials_file}")
            return True

        except (IOError, OSError) as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def clear_credentials(self) -> bool:
        """Remove stored credentials"""
        try:
            if self.credentials_file.exists():
                self.credentials_file.unlink()
                logger.info("Stored credentials cleared")
                return True
            else:
                logger.info("No stored credentials found")
                return True

        except OSError as e:
            logger.error(f"Failed to clear credentials: {e}")
            return False

    def has_stored_credentials(self) -> bool:
        """Check if credentials are stored in config file"""
        username, password = self._load_from_config()
        return bool(username and password)

    def get_credential_sources(self) -> Dict[str, Any]:
        """Get information about available credential sources for debugging"""
        sources = {
            'environment_variables': {
                'username': bool(os.environ.get('EQUASIS_USERNAME')),
                'password': bool(os.environ.get('EQUASIS_PASSWORD'))
            },
            'config_file': {
                'path': str(self.credentials_file),
                'exists': self.credentials_file.exists(),
                'has_credentials': self.has_stored_credentials()
            },
            'config_directory': {
                'path': str(self.config_dir),
                'exists': self.config_dir.exists()
            }
        }

        return sources

    def interactive_setup(self) -> bool:
        """
        Interactively collect and save credentials

        Returns:
            True if credentials were saved successfully
        """
        print()
        print("=== Equasis CLI Credential Setup ===")
        print()
        print("This will securely store your Equasis credentials for future use.")
        print(f"Credentials will be saved to: {self.credentials_file}")
        print()

        try:
            username = input("Equasis Username: ").strip()
            if not username:
                print("Username cannot be empty")
                return False

            password = getpass.getpass("Equasis Password: ").strip()
            if not password:
                print("Password cannot be empty")
                return False

            # Confirm before saving
            print()
            confirm = input(f"Save credentials to {self.credentials_file}? [y/N]: ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("Setup cancelled")
                return False

            # Save credentials
            success = self.save_credentials(username, password)

            if success:
                print()
                print("✓ Credentials saved successfully!")
                print("  You can now use equasis commands without --username/--password flags")
                print()
                print("Security notes:")
                print(f"  • File permissions set to owner-only (600)")
                print(f"  • To remove credentials later: equasis configure --clear")
                print()
                return True
            else:
                print("✗ Failed to save credentials")
                return False

        except KeyboardInterrupt:
            print()
            print("Setup cancelled by user")
            return False
        except Exception as e:
            print(f"Error during setup: {e}")
            return False


def get_credential_manager() -> CredentialManager:
    """Get a credential manager instance"""
    return CredentialManager()
