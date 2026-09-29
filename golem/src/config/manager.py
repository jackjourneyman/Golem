"""
Configuration Manager (read-only)

Golem is a documentation and question-answering agent. It reads the Home
Assistant configuration and curated files, and it never writes to them:
write access is blocked by the add-on volume mappings (read_only) and by
AppArmor. This module therefore exposes only read operations.

Everything inherited from the parent project that existed solely to support
writes has been removed:
- write_file_raw and the atomic-write/rollback machinery
- backup creation, rotation, listing and restore
- device/entity/area/Lovelace registry writes (custom-component and
  WebSocket variants)
- validate_config (only meaningful immediately after a write)
- ruamel.yaml comment-preserving round-tripping (only needed to rewrite
  YAML files faithfully)

Public API kept: read_file_raw, file_exists, list_config_files.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Base exception for configuration access errors."""


class ConfigurationManager:
    """
    Read-only access to the Home Assistant configuration directory.

    The manager deliberately contains no write methods. All file access is
    funnelled through _validate_path(), which confines every operation to
    the configuration directory and blocks path traversal (for example
    "../../etc/passwd").
    """

    # Hard limit on the size of a single file returned to the caller.
    # This protects the LLM context window from very large files such as
    # a home-assistant_v2.db export or a giant secrets file.
    MAX_FILE_CHARS = 500_000

    def __init__(self, config_dir: str):
        """
        Initialize the read-only configuration manager.

        Args:
            config_dir: Path to the Home Assistant config directory
                        (typically /homeassistant inside the add-on).
        """
        self.config_dir = Path(config_dir).resolve()

        # No backup directory, no hass instance, no ruamel.yaml: those
        # existed only to support writes in the parent project.
        logger.info("ConfigurationManager initialised (read-only):")
        logger.info(f"  Config dir: {self.config_dir}")

    # ------------------------------------------------------------------
    # Path handling
    # ------------------------------------------------------------------

    def _validate_path(self, file_path: str) -> Path:
        """
        Validate and resolve a relative path against the config directory.

        This is the security boundary of the whole module. It:
        1. Resolves the path (collapsing '..' and symlinks where possible).
        2. Confirms the result lies inside the config directory.
        Any attempt to escape the directory raises ConfigurationError.

        Args:
            file_path: Relative path to a config file (e.g. "automations.yaml")

        Returns:
            Resolved absolute Path object.

        Raises:
            ConfigurationError: If path is empty or outside config_dir.
        """
        if not file_path or file_path.strip() == "":
            raise ConfigurationError("Empty file path")

        # Resolve relative path against config_dir
        full_path = (self.config_dir / file_path).resolve()

        # Ensure path is within config_dir (prevents path traversal)
        if not str(full_path).startswith(str(self.config_dir)):
            raise ConfigurationError(
                f"Invalid path: {file_path} is outside config directory"
            )

        return full_path

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def read_file_raw(
        self, file_path: str, allow_missing: bool = False
    ) -> Optional[str]:
        """
        Read a configuration file as raw text, without any parsing.

        Raw text is returned deliberately: the agent answers questions and
        produces documentation, so preserving comments and formatting is
        more valuable than a parsed structure.

        Args:
            file_path: Relative path to the file (e.g., "configuration.yaml")
            allow_missing: If True, return None for missing files instead
                           of raising; useful when probing for optional files.

        Returns:
            File content as a string, or None if the file does not exist
            and allow_missing is True.

        Raises:
            ConfigurationError: If the path is invalid, the file is missing
            (and allow_missing is False), or the file cannot be read.
        """
        full_path = self._validate_path(file_path)

        if not full_path.exists():
            if allow_missing:
                logger.debug(f"File not found (allowed): {file_path}")
                return None
            raise ConfigurationError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ConfigurationError(f"Not a file: {file_path}")

        try:
            logger.debug(f"Reading raw config file: {file_path}")
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError as e:
            raise ConfigurationError(f"Error reading {file_path}: {str(e)}")

    async def file_exists(self, file_path: str) -> bool:
        """
        Check whether a file exists inside the config directory.

        Useful for the agent to probe for optional files (packages,
        custom prompt files, etc.) without triggering exceptions.

        Args:
            file_path: Relative path to check.

        Returns:
            True if the path exists and is a file.
        """
        try:
            full_path = self._validate_path(file_path)
        except ConfigurationError:
            return False
        return full_path.is_file()

    async def list_config_files(
        self,
        pattern: str = "*",
        relative: bool = True,
        recursive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List files in the config directory matching a glob pattern.

        New in Golem: this supports the documentation use case, letting the
        agent enumerate the configuration tree (for example all YAML files
        under /packages) before deciding what to read in full.

        Args:
            pattern: Glob pattern (e.g. "*.yaml", "scripts/*.yaml").
            relative: If True, return paths relative to the config dir.
            recursive: If True, recurse into subdirectories ("**" in the
                       pattern is also honoured by pathlib).

        Returns:
            List of dicts with keys:
                - path: file path (relative or absolute per the flag)
                - size: file size in bytes
            Sorted by path for stable, predictable output.
        """
        glob_pattern = f"**/{pattern}" if recursive else pattern

        try:
            matches = self.config_dir.glob(glob_pattern)
            results = []
            for p in sorted(matches):
                if not p.is_file():
                    continue
                results.append({
                    "path": str(p.relative_to(self.config_dir)) if relative
                            else str(p),
                    "size": p.stat().st_size,
                })
            logger.debug(
                f"Listed {len(results)} file(s) matching '{glob_pattern}'"
            )
            return results
        except OSError as e:
            raise ConfigurationError(
                f"Error listing files for pattern '{pattern}': {str(e)}"
            )