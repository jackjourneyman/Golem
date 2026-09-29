"""
Home Assistant WebSocket API Client (read-only).

Golem answers questions about the Home Assistant instance and compiles
documentation. The WebSocket API is used for information that is not
available as a file under /config, such as the Lovelace dashboard stored
in the database (.storage) and the device, entity and area registries.

Read access only. Every write operation inherited from the parent project
has been removed:
- save_lovelace_config / save_lovelace_config_from_yaml
- update_device / update_entity
- create_area / update_area
- reload_config / reload_homeassistant_config

The remaining module-level helper, get_lovelace_config_as_yaml, is the
only consumer of ruamel.yaml in Golem. If you prefer to drop that
dependency, replace the ruamel dump in that function with a plain
`json.dumps(config, indent=2)` and remove ruamel from requirements.txt.
"""

import logging
from typing import Any, Dict, Optional, List
import aiohttp

logger = logging.getLogger(__name__)


class HomeAssistantWebSocket:
    """
    Client for the Home Assistant WebSocket API.

    Lifecycle: construct, await connect(), make one or more call()s (or
    the higher-level read methods), then await close(). One connection can
    carry any number of commands; the message_id counter ensures each
    response is matched to its request.
    """

    def __init__(self, url: str, token: str):
        """
        Initialize the WebSocket client.

        Args:
            url: Home Assistant WebSocket URL
                 (e.g., ws://supervisor/core/websocket in add-on mode)
            token: Long-lived access token or Supervisor token
        """
        self.url = url
        self.token = token
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.message_id = 1
        self.authenticated = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Establish the WebSocket connection and authenticate.

        Home Assistant's WebSocket handshake is a three-step protocol:
        1. The server announces auth_required on connect.
        2. The client replies with its access token.
        3. The server confirms with auth_ok (or refuses).

        On any failure the partial connection is closed before the
        exception is re-raised, so no socket or session is leaked.
        """
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.url)
            logger.info("WebSocket connection established")

            # Step 1: wait for the server's auth challenge.
            msg = await self.ws.receive_json()
            if msg.get("type") != "auth_required":
                raise Exception(f"Unexpected message type: {msg.get('type')}")

            # Step 2: present the token.
            await self.ws.send_json({
                "type": "auth",
                "access_token": self.token
            })

            # Step 3: confirm the outcome.
            auth_response = await self.ws.receive_json()
            if auth_response.get("type") == "auth_ok":
                self.authenticated = True
                logger.info("WebSocket authentication successful")
            else:
                raise Exception(f"Authentication failed: {auth_response}")

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self.close()
            raise

    async def close(self) -> None:
        """Close the WebSocket and its underlying HTTP session."""
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        self.authenticated = False
        logger.info("WebSocket connection closed")

    # ------------------------------------------------------------------
    # Command transport
    # ------------------------------------------------------------------

    async def call(self, message_type: str, **kwargs) -> Dict[str, Any]:
        """
        Send one WebSocket command and wait for its matching response.

        This is the single transport primitive used by every read method
        below. Messages are correlated by incrementing message_id; the
        receive loop discards nothing because Home Assistant only sends
        event frames for subscriptions, which this client does not create.

        Args:
            message_type: Command type (e.g., "lovelace/config")
            **kwargs: Additional command parameters

        Returns:
            The command's result payload.

        Raises:
            Exception: If not authenticated, or the command fails.
        """
        if not self.authenticated or not self.ws:
            raise Exception("WebSocket not authenticated")

        msg_id = self.message_id
        self.message_id += 1

        # Send the command tagged with its message id.
        message = {
            "id": msg_id,
            "type": message_type,
            **kwargs
        }
        await self.ws.send_json(message)
        logger.debug(f"Sent WebSocket message: {message}")

        # Wait for the result frame carrying the same id.
        while True:
            response = await self.ws.receive_json()
            logger.debug(f"Received WebSocket message: {response}")

            if response.get("id") == msg_id:
                if response.get("type") == "result":
                    if response.get("success", True):
                        return response.get("result", {})
                    else:
                        error = response.get("error", {})
                        raise Exception(f"WebSocket call failed: {error}")
                else:
                    raise Exception(f"Unexpected response type: {response.get('type')}")

    # ------------------------------------------------------------------
    # Read operations: Lovelace
    # ------------------------------------------------------------------

    async def get_lovelace_config(self) -> Dict[str, Any]:
        """
        Retrieve the Lovelace dashboard configuration.

        The dashboard is stored in the database (.storage), not in a file
        under /config, so this WebSocket read is the only way for the
        agent to see it.

        Returns:
            Lovelace configuration as a dictionary.

        Raises:
            Exception: If retrieval fails.
        """
        logger.info("Retrieving Lovelace configuration via WebSocket")
        try:
            config = await self.call("lovelace/config", force=False)
            logger.info("Successfully retrieved Lovelace configuration")
            return config
        except Exception as e:
            logger.error(f"Failed to retrieve Lovelace config: {e}")
            raise

    # ------------------------------------------------------------------
    # Read operations: registries
    # ------------------------------------------------------------------

    async def list_devices(self) -> List[Dict[str, Any]]:
        """
        List all devices from the device registry.

        Returns:
            List of device dictionaries.

        Raises:
            Exception: If request fails.
        """
        logger.info("Retrieving device registry via WebSocket")
        try:
            devices = await self.call("config/device_registry/list")
            logger.info(f"Successfully retrieved {len(devices)} devices")
            return devices
        except Exception as e:
            logger.error(f"Failed to retrieve device registry: {e}")
            raise

    async def list_entities(self) -> List[Dict[str, Any]]:
        """
        List all entities from the entity registry.

        Returns:
            List of entity dictionaries.

        Raises:
            Exception: If request fails.
        """
        logger.info("Retrieving entity registry via WebSocket")
        try:
            entities = await self.call("config/entity_registry/list")
            logger.info(f"Successfully retrieved {len(entities)} entities")
            return entities
        except Exception as e:
            logger.error(f"Failed to retrieve entity registry: {e}")
            raise

    async def list_entities_for_display(self) -> List[Dict[str, Any]]:
        """
        List entities with display information (including state).

        Returns:
            List of entity dictionaries enriched for display.

        Raises:
            Exception: If request fails.
        """
        logger.info("Retrieving entity registry for display via WebSocket")
        try:
            entities = await self.call("config/entity_registry/list_for_display")
            logger.info(f"Successfully retrieved {len(entities)} entities for display")
            return entities
        except Exception as e:
            logger.error(f"Failed to retrieve entity registry for display: {e}")
            raise

    async def list_areas(self) -> List[Dict[str, Any]]:
        """
        List all areas from the area registry.

        The result is normalised to a list because older Home Assistant
        versions wrap registry listings in an object.

        Returns:
            List of area dictionaries.
        """
        logger.info("Retrieving area registry via WebSocket")
        try:
            result = await self.call("config/area_registry/list")
            areas = result if isinstance(result, list) else []
            logger.info(f"Successfully retrieved {len(areas)} areas")
            return areas
        except Exception as e:
            logger.error(f"Failed to retrieve area registry: {e}")
            raise


# ----------------------------------------------------------------------
# Module-level convenience helpers
# ----------------------------------------------------------------------
# These open a short-lived connection, perform one read and close again,
# so callers (src/agents/tools.py) do not have to manage the lifecycle.

async def get_lovelace_config_as_yaml(url: str, token: str) -> Optional[str]:
    """
    Retrieve the Lovelace configuration as a YAML string.

    The agent presents configuration to the user (and to the LLM) in YAML
    form, matching how the rest of /config is displayed. Returns None on
    failure rather than raising, so the agent tool layer can degrade to
    a friendly error message.

    Args:
        url: WebSocket URL
        token: Access token

    Returns:
        YAML string of the Lovelace config, or None if retrieval fails.
    """
    ws_client = HomeAssistantWebSocket(url, token)
    try:
        await ws_client.connect()
        config = await ws_client.get_lovelace_config()

        # Serialise the dict to YAML. This is the only remaining use of
        # ruamel.yaml in Golem; see the module docstring if you wish to
        # replace it and drop the dependency.
        from ruamel.yaml import YAML
        from io import StringIO

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.preserve_quotes = True
        yaml.width = 4096

        stream = StringIO()
        yaml.dump(config, stream)
        return stream.getvalue()

    except Exception as e:
        logger.error(f"Failed to get Lovelace config: {e}")
        return None
    finally:
        await ws_client.close()