"""
AI Agent Tool Functions (read-only).

These are the tools exposed to the LLM. They wrap the read-only
ConfigurationManager and the read-only Home Assistant WebSocket client, so
the agent can inspect the instance's configuration and registries, answer
questions about it and compile documentation.

Changes from the parent project (which could write to /config):
- Removed the propose_config_changes tool: with write access removed there
  is no approval workflow, so the model must not be offered a tool that
  stages changes.
- Removed the workflow and agent_system constructor parameters: they existed
  to hand proposed changes to the (now deleted) approval pipeline. The
  stale ValidationWorkflow reference to a nonexistent module is gone too.
- Removed every custom-component (hass API) branch: Golem runs only as an
  add-on, so the WebSocket path is the only path.

Two tools remain, both read-only:
- read_config_file: fetch one known file (or one virtual registry entry)
- search_config_files: find files (and virtual entries) matching a narrow
  search pattern or a '/path' glob

Both tools bound their responses: per-file content is capped and the number
of files per search is capped, protecting the model context window.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import ConfigurationManager
from ..ha.ha_websocket import HomeAssistantWebSocket, get_lovelace_config_as_yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bounds for agent tool responses (protect the model context window)
# ---------------------------------------------------------------------------
# Two separate caps serve two different purposes:
#
# MAX_READ_CHARS applies to read_config_file, which returns ONE file. Curated
# documentation and integration reports can be large, and the agent needs to
# see them whole, so this cap is generous.
#
# MAX_CONTENT_CHARS applies within search_config_files results, where up to
# MAX_FILES_PER_SEARCH files are returned in ONE response. This cap must stay
# conservative: the worst case is MAX_FILES_PER_SEARCH * MAX_CONTENT_CHARS
# characters in a single tool result, which overflows the model context if
# allowed to grow. (The 0.3.0 broad-pattern guards exist for the same reason.)

MAX_READ_CHARS = 60000        # per-file cap for direct reads (read_config_file)
MAX_CONTENT_CHARS = 8000       # per-file cap within search results
MAX_FILES_PER_SEARCH = 20      # max number of files returned per search

# Patterns that would match a large share of the configuration and risk
# overflowing the model context. Rejected outright (case-insensitive).

BROAD_PATTERNS = {
    "light", "lights", "lighting", "sensor", "sensors", "binary",
    "switch", "switches", "automation", "automations", "script", "scripts",
    "template", "templates", "config", "configuration", "yaml", "yml",
    "on", "off", "input", "device", "devices", "entity", "entities",
    "area", "areas", "zone", "zones", "timer", "timers",
}


class AgentTools:
    """
    Read-only tool functions for the AI agent.

    All tools provide:
    - Structured dict responses with a 'success' flag and an 'error' key
      on failure, so the model receives friendly errors, not exceptions
    - Bounded content (never the whole configuration in one response)
    - Logging of every operation for auditability
    """

    def __init__(self, config_manager: ConfigurationManager):
        """
        Initialize agent tools with the read-only configuration manager.

        Args:
            config_manager: ConfigurationManager instance for file access
        """
        self.config_manager = config_manager
        # Cache the Lovelace config for the lifetime of the process to
        # avoid repeated Supervisor WebSocket calls within one session.
        self._lovelace_cache: Optional[str] = None
        logger.info("AgentTools initialized (read-only)")

    # ------------------------------------------------------------------
    # Internal helpers: Home Assistant registries
    # ------------------------------------------------------------------
    # These helpers talk to the Home Assistant WebSocket API via the
    # Supervisor proxy. They always return empty results (not exceptions)
    # on failure, so a missing registry never breaks a chat response.

    async def _get_lovelace_config(self) -> Optional[str]:
        """
        Retrieve the Lovelace dashboard configuration as YAML.

        Cached after the first successful call. Returns None if the
        config is unavailable (no Supervisor token, dashboard in YAML
        mode rather than storage mode, or a connection failure).

        Returns:
            YAML string of the Lovelace config, or None.
        """
        if self._lovelace_cache:
            return self._lovelace_cache

        try:
            supervisor_token = os.getenv('SUPERVISOR_TOKEN')
            if not supervisor_token:
                logger.debug("No SUPERVISOR_TOKEN available, skipping Lovelace config")
                return None

            ws_url = "ws://supervisor/core/websocket"
            lovelace_yaml = await get_lovelace_config_as_yaml(ws_url, supervisor_token)
            if lovelace_yaml:
                self._lovelace_cache = lovelace_yaml
                logger.info("Successfully retrieved Lovelace config via WebSocket")
            return lovelace_yaml
        except Exception as e:
            logger.debug(f"Failed to get Lovelace config: {e}")
            return None

    async def _get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Retrieve all devices from the device registry.

        Returns:
            List of device dictionaries (empty on any failure).
        """
        try:
            supervisor_token = os.getenv('SUPERVISOR_TOKEN')
            if not supervisor_token:
                logger.debug("No SUPERVISOR_TOKEN available, skipping devices")
                return []

            ws_client = HomeAssistantWebSocket("ws://supervisor/core/websocket", supervisor_token)
            await ws_client.connect()
            try:
                return await ws_client.list_devices()
            finally:
                await ws_client.close()
        except Exception as e:
            logger.debug(f"Failed to get devices: {e}")
            return []

    async def _get_all_entities(self) -> List[Dict[str, Any]]:
        """
        Retrieve all entities from the entity registry.

        Returns:
            List of entity dictionaries (empty on any failure).
        """
        try:
            supervisor_token = os.getenv('SUPERVISOR_TOKEN')
            if not supervisor_token:
                logger.debug("No SUPERVISOR_TOKEN available, skipping entities")
                return []

            ws_client = HomeAssistantWebSocket("ws://supervisor/core/websocket", supervisor_token)
            await ws_client.connect()
            try:
                return await ws_client.list_entities()
            finally:
                await ws_client.close()
        except Exception as e:
            logger.debug(f"Failed to get entities: {e}")
            return []

    async def _get_all_areas(self) -> List[Dict[str, Any]]:
        """
        Retrieve all areas from the area registry.

        Returns:
            List of area dictionaries (empty on any failure).
        """
        try:
            supervisor_token = os.getenv('SUPERVISOR_TOKEN')
            if not supervisor_token:
                logger.debug("No SUPERVISOR_TOKEN available, skipping areas")
                return []

            ws_client = HomeAssistantWebSocket("ws://supervisor/core/websocket", supervisor_token)
            await ws_client.connect()
            try:
                return await ws_client.list_areas()
            finally:
                await ws_client.close()
        except Exception as e:
            logger.debug(f"Failed to get areas: {e}")
            return []

    # ------------------------------------------------------------------
    # Internal helper: response bounding
    # ------------------------------------------------------------------

    def _bounded_file_entry(
        self,
        path: str,
        content: str,
        matches: Optional[int]
    ) -> Dict[str, Any]:
        """
        Build a file result entry with content capped at MAX_CONTENT_CHARS.

        Args:
            path: Relative file path (or virtual path, e.g. 'devices/x.json')
            content: Full file content
            matches: Number of pattern matches (or None if not a search)

        Returns:
            Dict with path, bounded content, matches and a truncated flag.
        """
        return {
            "path": path,
            "content": content[:MAX_CONTENT_CHARS],
            "matches": matches,
            "truncated": len(content) > MAX_CONTENT_CHARS,
        }

    # ------------------------------------------------------------------
    # Tool: read a single file
    # ------------------------------------------------------------------

    async def read_config_file(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Read a single configuration file by relative path.

        Use this in preference to search when the target file is already
        known (for example when the user names it, or when following a
        reference found by a previous search). Content is capped at
        MAX_READ_CHARS (the generous single-file cap) and a 'truncated'
        flag is set if the file was longer. A file truncated in a search
        result can be re-read in full here up to MAX_READ_CHARS.

        In addition to real files under /config, four families of virtual
        files are accepted and resolved against the live registries:
        - 'lovelace.yaml'          -> the Lovelace dashboard
        - 'devices/<device_id>.json' -> one device registry entry
        - 'entities/<entity_id>.json'-> one entity registry entry
        - 'areas/<area_id>.json'     -> one area registry entry

        Args:
            file_path: Required. Relative path (e.g. 'automations.yaml').

        Returns:
            Dict with:
                - success: bool
                - path: str
                - content: str (capped at MAX_CONTENT_CHARS)
                - truncated: bool
                - error: Optional[str]
        """
        try:
            logger.info(f"Agent reading file: '{file_path}'")

            if not file_path or not file_path.strip():
                return {
                    "success": False,
                    "error": "file_path is required."
                }

            # Normalise: strip whitespace and any leading slash so the
            # path is always relative to the config directory.
            file_path = file_path.strip().lstrip("/")

            # --- Virtual files (registry / dashboard) -----------------
            if file_path == "lovelace.yaml":
                content = await self._get_lovelace_config()
                if not content:
                    return {
                        "success": False,
                        "error": "Could not retrieve lovelace.yaml"
                    }
            elif file_path.startswith("devices/"):
                device_id = file_path.replace("devices/", "").replace(".json", "")
                devices = await self._get_all_devices()
                device = next((d for d in devices if d.get('id') == device_id), None)
                if not device:
                    return {
                        "success": False,
                        "error": f"Device {device_id} not found in registry"
                    }
                content = json.dumps(device, indent=2)
            elif file_path.startswith("entities/"):
                entity_id = file_path.replace("entities/", "").replace(".json", "")
                entities = await self._get_all_entities()
                entity = next((e for e in entities if e.get('entity_id') == entity_id), None)
                if not entity:
                    return {
                        "success": False,
                        "error": f"Entity {entity_id} not found in registry"
                    }
                content = json.dumps(entity, indent=2)
            elif file_path.startswith("areas/"):
                area_id = file_path.replace("areas/", "").replace(".json", "")
                areas = await self._get_all_areas()
                area = next((a for a in areas if a.get('area_id') == area_id), None)
                if not area:
                    return {
                        "success": False,
                        "error": f"Area {area_id} not found in registry"
                    }
                content = json.dumps(area, indent=2)

            # --- Real file under /config -------------------------------
            else:
                content = await self.config_manager.read_file_raw(file_path)
                if content is None:
                    return {
                        "success": False,
                        "error": f"File not found: {file_path}"
                    }

            return {
                "success": True,
                "path": file_path,
                "content": content[:MAX_READ_CHARS],
                "truncated": len(content) > MAX_READ_CHARS
            }

        except Exception as e:
            logger.error(f"Agent error reading file {file_path}: {e}")
            return {
                "success": False,
                "error": f"Error reading file: {str(e)}",
                "path": file_path
            }

    # ------------------------------------------------------------------
    # Tool: search configuration files
    # ------------------------------------------------------------------

    async def search_config_files(
        self,
        search_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search configuration files for a specific pattern and return
        matching files.

        The pattern MUST be a narrow, specific identifier: an entity_id,
        an automation/script id, a unique alias fragment, or a '/path'
        file pattern. Empty patterns and broad topic words are rejected
        by server-side validation. Returned file contents are capped at
        MAX_CONTENT_CHARS per file and MAX_FILES_PER_SEARCH files per call.

        Searching covers all YAML and .txt files (excluding
        custom_components and secrets.yaml) plus the virtual files
        (lovelace.yaml, devices, entities, areas).

        Args:
            search_pattern: Required. Text to search for in file contents
                          and filenames. Case-insensitive.
                          If it starts with '/', it is treated as a file
                          path glob and only real files are searched.

        Returns:
            Dict with:
                - success: bool
                - files: List[Dict] with keys:
                    - path: str (relative file path)
                    - content: str (bounded file content)
                    - matches: Optional[int]
                    - truncated: bool
                - count: int (number of files returned)
                - omitted_paths: Optional[List[str]] (beyond the cap)
                - note: Optional[str]
                - search_pattern: Optional[str]
                - error: Optional[str]
        """
        try:
            # --- Validation: hard gate on the search pattern -----------
            # These guards were added in the parent project after broad
            # searches (e.g. 'automation') overflowed the model context.
            # They are retained unchanged: Golem still needs them.
            #
            # Rejections carry 'rejected': True so the front end can show
            # them as informational notices rather than errors; the model
            # still sees success=False and does not retry the pattern.
            if not search_pattern or not search_pattern.strip():
                logger.warning("Agent search rejected: empty search_pattern")
                return {
                    "success": False,
                    "rejected": True,
                    "error": (
                        "search_pattern is required. Provide a specific "
                        "entity_id (e.g. 'light.kitchen'), an automation/script id, "
                        "a unique alias fragment, or a '/path' file pattern. "
                        "Do not retry without a specific pattern."
                    ),
                }

            search_pattern = search_pattern.strip()

            if not search_pattern.startswith("/"):
                if search_pattern.lower() in BROAD_PATTERNS:
                    logger.warning(f"Agent search rejected: broad pattern '{search_pattern}'")
                    return {
                        "success": False,
                        "rejected": True,
                        "error": (
                            f"Pattern '{search_pattern}' is too broad and would match "
                            "many files. Use a specific entity_id (e.g. 'light.kitchen'), "
                            "an automation/script id, or a unique alias fragment. "
                            "Broad topic words are not accepted."
                        ),
                    }
                if len(search_pattern) < 4:
                    logger.warning(f"Agent search rejected: pattern '{search_pattern}' shorter than 4 characters")
                    return {
                        "success": False,
                        "rejected": True,
                        "error": (
                            f"Pattern '{search_pattern}' is too short and likely broad. "
                            "Use a specific entity_id, automation/script id, or a "
                            "unique alias fragment (at least 4 characters)."
                        ),
                    }

            logger.info(f"Agent searching all files - pattern: '{search_pattern}'")
            config_dir = self.config_manager.config_dir

            # --- Step 1: assemble the candidate real files -------------
            # A leading '/' means the pattern is a glob of file paths, so
            # no content matching is done; otherwise all YAML and txt
            # files are candidates for a content search.
            is_file_path_pattern = search_pattern.startswith("/")

            if is_file_path_pattern:
                glob_pattern = search_pattern.lstrip("/")
                matched_paths = list(config_dir.glob(glob_pattern))
                logger.info(f"File path pattern matched {len(matched_paths)} files")
            else:
                matched_paths = (
                    list(config_dir.glob("**/*.yaml"))
                    + list(config_dir.glob("**/*.txt"))
                )

            # Filter: real files only; exclude custom_components (third-
            # party code, not the user's configuration) and secrets.yaml
            # (0.1.7: prevent leaking secrets to the LLM).
            matched_paths = [
                p for p in matched_paths
                if p.is_file()
                and 'custom_components' not in p.parts
                and 'secrets.yaml' not in p.parts
            ]
            matched_paths.sort()  # deterministic ordering across calls

            # --- Step 2: content-match the real files -------------------
            files: List[Dict[str, Any]] = []
            for path in matched_paths:
                relative_path = str(path.relative_to(config_dir))
                try:
                    content = await self.config_manager.read_file_raw(relative_path)

                    if is_file_path_pattern:
                        # Glob match: include without content filtering.
                        files.append(self._bounded_file_entry(relative_path, content, 1))
                    else:
                        # Count case-insensitive occurrences in both the
                        # content and the filename itself.
                        content_matches = len(re.findall(
                            re.escape(search_pattern), content, re.IGNORECASE))
                        filename_matches = len(re.findall(
                            re.escape(search_pattern), relative_path, re.IGNORECASE))
                        total_matches = content_matches + filename_matches

                        if total_matches > 0:
                            files.append(self._bounded_file_entry(
                                relative_path, content, total_matches))

                except Exception as e:
                    logger.warning(f"Could not read {relative_path}: {e}")
                    continue

            # --- Step 3: search the virtual (registry) files -----------
            # Registry entries are presented as virtual JSON files so the
            # search space is uniform for the model. Skipped entirely when
            # a file path glob was requested.
            if not is_file_path_pattern:
                await self._search_virtual_files(search_pattern, files)

            logger.info(f"Agent found {len(files)} files (searched {len(matched_paths)} YAML/txt files + virtual files)")

            # --- Step 4: bound the number of files returned ------------
            omitted_paths = []
            if len(files) > MAX_FILES_PER_SEARCH:
                omitted_paths = [f["path"] for f in files[MAX_FILES_PER_SEARCH:]]
                logger.warning(
                    f"Search returned {len(files)} files; capping at "
                    f"{MAX_FILES_PER_SEARCH} and omitting {len(omitted_paths)}"
                )
                files = files[:MAX_FILES_PER_SEARCH]

            result = {
                "success": True,
                "files": files,
                "count": len(files)
            }

            # If files were dropped, tell the model which paths exist so
            # it can read them individually rather than re-searching.
            if omitted_paths:
                result["omitted_paths"] = omitted_paths
                result["note"] = (
                    f"{len(omitted_paths)} additional matching files were omitted to stay "
                    "within limits. Refine the search pattern to narrow the result, or read "
                    "specific files individually."
                )

            result["search_pattern"] = search_pattern
            return result

        except Exception as e:
            logger.error(f"Agent error searching config files: {e}")
            return {
                "success": False,
                "error": f"Error searching files: {str(e)}",
                "search_pattern": search_pattern
            }

    # ------------------------------------------------------------------
    # Internal helper: search the virtual registry files
    # ------------------------------------------------------------------

    async def _search_virtual_files(
        self,
        search_pattern: str,
        files: List[Dict[str, Any]]
    ) -> None:
        """
        Search the virtual (registry/dashboard) files and append matches
        to the files list in place.

        Each registry entry is serialised to JSON and matched against the
        pattern in both content and its virtual path name, exactly like a
        real file. All failures are non-fatal: a missing registry just
        contributes no results.

        Args:
            search_pattern: The (already validated) search pattern.
            files: The results list to append to.
        """
        # Device registry as devices/<id>.json
        try:
            devices = await self._get_all_devices()
            for device in devices:
                device_id = device.get('id', 'unknown')
                device_path = f"devices/{device_id}.json"
                device_json = json.dumps(device, indent=2)
                total = (
                    len(re.findall(re.escape(search_pattern), device_json, re.IGNORECASE))
                    + len(re.findall(re.escape(search_pattern), device_path, re.IGNORECASE))
                )
                if total > 0:
                    files.append(self._bounded_file_entry(device_path, device_json, total))
        except Exception as e:
            logger.debug(f"Could not retrieve devices (not critical): {e}")

        # Entity registry as entities/<entity_id>.json
        try:
            entities = await self._get_all_entities()
            for entity in entities:
                entity_id = entity.get('entity_id', 'unknown')
                entity_path = f"entities/{entity_id}.json"
                entity_json = json.dumps(entity, indent=2)
                total = (
                    len(re.findall(re.escape(search_pattern), entity_json, re.IGNORECASE))
                    + len(re.findall(re.escape(search_pattern), entity_path, re.IGNORECASE))
                )
                if total > 0:
                    files.append(self._bounded_file_entry(entity_path, entity_json, total))
        except Exception as e:
            logger.debug(f"Could not retrieve entities (not critical): {e}")

        # Area registry as areas/<area_id>.json
        try:
            areas = await self._get_all_areas()
            for area in areas:
                area_id = area.get('area_id', 'unknown')
                area_path = f"areas/{area_id}.json"
                area_json = json.dumps(area, indent=2)
                total = (
                    len(re.findall(re.escape(search_pattern), area_json, re.IGNORECASE))
                    + len(re.findall(re.escape(search_pattern), area_path, re.IGNORECASE))
                )
                if total > 0:
                    files.append(self._bounded_file_entry(area_path, area_json, total))
        except Exception as e:
            logger.debug(f"Could not retrieve areas (not critical): {e}")

        # Lovelace dashboard as lovelace.yaml
        try:
            lovelace_content = await self._get_lovelace_config()
            if lovelace_content:
                lovelace_path = "lovelace.yaml"
                total = (
                    len(re.findall(re.escape(search_pattern), lovelace_content, re.IGNORECASE))
                    + len(re.findall(re.escape(search_pattern), lovelace_path, re.IGNORECASE))
                )
                if total > 0:
                    files.append(self._bounded_file_entry(lovelace_path, lovelace_content, total))
        except Exception as e:
            logger.debug(f"Could not retrieve lovelace.yaml (not critical): {e}")
