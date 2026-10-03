"""
Application entry point for the Golem add-on.

Golem is a read-only documentation and question-answering agent for a Home
Assistant instance. This module wires together the FastAPI web server, the
read-only ConfigurationManager and the AgentSystem.

Changes from the parent project (which could write to /config):
- Removed POST /api/approve and the ApprovalRequest model: there is no
  changeset approval workflow because there is nothing to approve.
- Removed RestoreBackupRequest: it was unused (no restore endpoint existed)
  and backups are meaningless without writes.
- Removed ChatRequest and the pydantic import: the WebSocket endpoint reads
  raw JSON directly, so the model duplicated the protocol for nothing.
- Removed set_hass_instance(): Golem runs only as an add-on, never as a
  custom component, so there is no hass instance to inject.
- ConfigurationManager is constructed with config_dir only; the backup_dir
  argument is gone together with the backup directory itself.
- Updated branding from "AI Configuration Agent" to Golem, matching the
  add-on's current purpose.

The WebSocket chat endpoint (/ws/chat) is retained unchanged in behaviour:
it is the primary interface between the front end and the agent.
"""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from typing import Optional
import os
import logging
from datetime import datetime
import json as json_lib

from .config import ConfigurationManager
from .agents import AgentSystem

version = "0.5.3"

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
# Read the log level from the add-on options (exported as an environment
# variable by run.sh) and configure process-wide logging before anything
# else runs.
log_level = os.getenv('LOG_LEVEL', 'info').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global application state
# ---------------------------------------------------------------------------
# Single instances shared by all endpoints, created once during lifespan
# startup below rather than per request. Optional because the app may
# start (and serve /health) even if initialisation partially fails.
config_manager: Optional[ConfigurationManager] = None
agent_system: Optional[AgentSystem] = None


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Initialize the application on startup and clean up on shutdown.

    Startup does two things, in order:
    1. Create the read-only ConfigurationManager pointing at the Home
       Assistant configuration directory mapped into the add-on.
    2. Create the AgentSystem, loading a custom system prompt from the
       configuration directory if the user has configured one.

    Both failures are logged but not fatal: the server still starts so
    that /health can report what is missing and the logs are reachable
    through the Home Assistant add-on UI.
    """
    global config_manager, agent_system

    logger.info("=== Golem Starting ===")
    logger.info(f"OpenAI API URL: {os.getenv('OPENAI_API_URL', 'Not configured')}")
    logger.info(f"OpenAI Model: {os.getenv('OPENAI_MODEL', 'Not configured')}")
    logger.info(f"HA Config Dir: {os.getenv('HA_CONFIG_DIR', 'Not configured')}")
    logger.info(f"Log Level: {log_level}")

    # --- 1. Configuration manager (read-only) --------------------------
    try:
        config_manager = ConfigurationManager(
            config_dir=os.getenv('HA_CONFIG_DIR', '/config')
        )
        logger.info("Configuration manager initialized (read-only)")
    except Exception as e:
        logger.error(f"Failed to initialize configuration manager: {e}", exc_info=True)

    # --- 2. Agent system ----------------------------------------------
    try:
        if config_manager:
            # Load a custom system prompt from the HA config directory if
            # the user specified one. This lets the owner curate Golem's
            # behaviour (for example "focus on documenting automations").
            system_prompt = None
            system_prompt_file = os.getenv('SYSTEM_PROMPT_FILE')
            if system_prompt_file:
                try:
                    config_dir = os.getenv('HA_CONFIG_DIR', '/config')
                    prompt_path = os.path.join(config_dir, system_prompt_file)

                    # Security: ensure the prompt file lies inside the
                    # config directory, so the option cannot be used to
                    # read arbitrary files.
                    real_config = os.path.realpath(config_dir)
                    real_prompt = os.path.realpath(prompt_path)
                    if not real_prompt.startswith(real_config):
                        logger.error(f"System prompt file path {system_prompt_file} is outside config directory")
                    else:
                        with open(prompt_path, 'r') as f:
                            system_prompt = f.read()
                        logger.info(f"Loaded custom system prompt from {system_prompt_file}")
                except FileNotFoundError:
                    logger.warning(f"System prompt file not found: {system_prompt_file}, using default")
                except Exception as e:
                    logger.error(f"Error reading system prompt file: {e}, using default")

            # Prompt caching flag (only effective for providers that
            # support it, e.g. Anthropic Claude).
            enable_cache_control = os.getenv('ENABLE_CACHE_CONTROL', 'false').lower() in ('true', '1', 'yes')

            # Token usage reporting method, validated against the
            # supported set with a safe fallback.
            usage_tracking = os.getenv('USAGE_TRACKING', 'stream_options').lower()
            if usage_tracking not in ('stream_options', 'usage', 'disabled'):
                logger.warning(f"Invalid usage_tracking value '{usage_tracking}', defaulting to 'stream_options'")
                usage_tracking = 'stream_options'

            agent_system = AgentSystem(
                config_manager,
                system_prompt=system_prompt,
                enable_cache_control=enable_cache_control,
                usage_tracking=usage_tracking
            )
            logger.info("Agent system initialized")
        else:
            logger.warning("Agent system not initialized - config manager unavailable")
    except Exception as e:
        logger.error(f"Failed to initialize agent system: {e}")

    yield

    # Shutdown
    logger.info("=== Golem Shutting Down ===")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Golem",
    description="AI-powered read-only Home Assistant documentation agent",
    version=version,
    lifespan=lifespan
)


@app.middleware("http")
async def strip_double_slash_middleware(request: Request, call_next):
    """
    Remove a leading double slash from the request path.

    Home Assistant Ingress occasionally produces paths beginning with "//",
    which FastAPI would otherwise route as a distinct (404) path. Normalising
    them here keeps routing stable behind the Ingress proxy.
    """
    path = request.scope.get("path")
    if path and path.startswith("//"):
        request.scope["path"] = path[1:]

    return await call_next(request)


# ---------------------------------------------------------------------------
# Static files and templates
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """
    Health check endpoint for the Home Assistant watchdog and monitoring.

    Reports whether each subsystem initialized correctly, so an operator
    can diagnose a half-started add-on from the JSON response alone.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": version,
        "config_manager_ready": config_manager is not None,
        "agent_system_ready": agent_system is not None,
        "openai_configured": bool(os.getenv('OPENAI_API_KEY'))
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the chat interface."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": version
    })


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    Chat with the agent over a WebSocket.

    WebSocket streaming is used instead of SSE because the Home Assistant
    Ingress proxy buffers SSE responses, which broke progressive output in
    earlier versions of the parent project.

    Client sends:
        {"type": "chat", "message": "...", "conversation_history": [...]}

    Server sends zero or more events per message:
        {"event": "token" | "tool_call" | "tool_start" | "tool_result"
                  | "message_complete" | "complete" | "error",
         "data": {...}}
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        # One connection handles many messages in a loop, so the UI keeps a
        # single socket open for the whole session.
        while True:
            data = await websocket.receive_json()
            logger.info(f"WebSocket received: type={data.get('type')}, message_len={len(data.get('message', ''))}")

            # Protocol guard: only "chat" messages are accepted; anything
            # else is rejected without closing the socket.
            if data.get("type") != "chat":
                await websocket.send_json({
                    "event": "error",
                    "data": {"error": "Invalid message type"}
                })
                continue

            if not agent_system:
                await websocket.send_json({
                    "event": "error",
                    "data": {"error": "Agent system not initialized. Please configure OPENAI_API_KEY."}
                })
                continue

            # Stream the agent's events to the client as they are produced,
            # so tokens and tool activity appear in real time.
            try:
                async for event in agent_system.chat_stream(
                    user_message=data.get("message", ""),
                    conversation_history=data.get("conversation_history")
                ):
                    # chat_stream yields the event payload as a JSON string;
                    # parse it so send_json produces one well-formed frame.
                    event_data = event.get("data", "{}")
                    if isinstance(event_data, str):
                        event_data = json_lib.loads(event_data)

                    await websocket.send_json({
                        "event": event.get("event"),
                        "data": event_data
                    })
                    logger.debug(f"WebSocket sent: {event.get('event')}")

            except Exception as e:
                # A failure during one message stream is reported to the
                # client as an error event; the socket stays open for the
                # next message.
                logger.error(f"Stream error: {e}", exc_info=True)
                await websocket.send_json({
                    "event": "error",
                    "data": {"error": str(e)}
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
