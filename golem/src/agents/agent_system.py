"""
Agent System for Golem.

Golem is a read-only documentation and question-answering agent for a Home
Assistant instance. This module owns:
- The LLM client (any OpenAI-compatible API)
- The system prompt (default, or a user-curated file from /config)
- The chat streaming pipeline, including the tool-call loop
- The two read-only tools exposed to the model

Changes from the parent project (which could write to /config):
- Removed the Changeset dataclass, store_changeset, process_approval and
  the pending_changesets store: with writes impossible there is nothing to
  approve, and the entire approval pipeline is deleted.
- Removed propose_config_changes from the tool definitions and the tool
  dispatch loop.
- Rewrote the default system prompt: it previously directed the model to
  propose configuration changes. It now directs the model to answer
  questions and produce documentation, and to state plainly that it
  cannot modify configuration.
- AgentTools is constructed with the config manager only (the
  agent_system back-reference existed solely to store changesets).

The chat_stream event protocol is unchanged: token, tool_call,
tool_start, tool_result, message_complete, complete, error.
"""

import logging
import os
from typing import Dict, Any, Optional, List

from openai import AsyncOpenAI

from ..agents.tools import AgentTools
from ..config import ConfigurationManager

logger = logging.getLogger(__name__)


class AgentSystem:
    """
    LLM agent for read-only Home Assistant configuration analysis.

    Responsibilities:
    - Interpreting user questions about the Home Assistant instance
    - Reading configuration through the two read-only tools
    - Answering questions and compiling documentation
    """

    def __init__(
        self,
        config_manager: ConfigurationManager,
        system_prompt: Optional[str] = None,
        enable_cache_control: bool = False,
        usage_tracking: str = 'stream_options'
    ):
        """
        Initialize the agent system.

        Args:
            config_manager: Read-only ConfigurationManager for file access
            system_prompt: Optional custom system prompt. If not provided,
                           the Golem default prompt is used.
            enable_cache_control: Mark messages for prompt caching where the
                           provider supports it (e.g. Anthropic Claude).
            usage_tracking: How to request token usage from the API:
                - 'stream_options': stream_options.include_usage (OpenAI)
                - 'usage': usage.include (alternative format)
                - 'disabled': no usage tracking
        """
        self.config_manager = config_manager

        # Read-only tools; no back-reference is needed because there is
        # no changeset storage any more.
        self.tools = AgentTools(config_manager)

        # --- LLM client ------------------------------------------------
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("No OpenAI API key configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=os.getenv('OPENAI_API_URL', 'https://api.openai.com/v1')
            )

        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')

        # Optional temperature override; None means provider default.
        temperature_str = os.getenv('TEMPERATURE')
        self.temperature = float(temperature_str) if temperature_str else None

        self.enable_cache_control = enable_cache_control
        self.usage_tracking = usage_tracking

        logger.info(f"AgentSystem initialized with model: {self.model}")
        if self.temperature is not None:
            logger.info(f"Temperature: {self.temperature}")
        logger.info(f"Cache control: {'enabled' if self.enable_cache_control else 'disabled'}")
        logger.info(f"Usage tracking: {self.usage_tracking}")

        # System prompt: user-curated file (if provided) or the Golem
        # default. A custom prompt lets the owner steer documentation
        # style and scope without editing the add-on.
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        if system_prompt:
            logger.info(f"Using custom system prompt ({len(system_prompt)} characters)")
        else:
            logger.info("Using default system prompt")

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _get_default_system_prompt(self) -> str:
        """
        Get the default system prompt for Golem.

        The prompt matches the tool set exposed in chat_stream: two
        read-only tools. It instructs the model to decline modification
        requests rather than pretend to stage them, which is the correct
        behaviour now that no write path exists.
        """
        return """You are Golem, a read-only Home Assistant documentation and question-answering assistant.

Your role is to help users understand their Home Assistant instance by reading its configuration and registries, answering questions, and compiling documentation. You cannot modify the configuration: write access has been deliberately removed. If asked to create, change or delete automations, scripts, dashboards or any configuration, state plainly that Golem is read-only and answer instead by explaining how the user could make the change themselves.

Key Responsibilities:
1. **Understanding Questions**: Interpret questions about the Home Assistant instance, its configuration, automations, scripts, entities, devices and areas
2. **Reading Configuration**: Use the tools to examine configuration files and registries
3. **Explaining**: Explain what the configuration does, how parts relate to each other, and why something behaves the way it does
4. **Documenting**: When asked, compile clear documentation of the instance or parts of it

Available Tools:
- search_config_files: Search configuration for a specific identifier (use this first when you do not know which files are relevant)
- read_config_file: Read one known file in full

Important Guidelines:
- Always read the relevant configuration before answering questions about it
- Search terms are case-insensitive; do not search for multiple case variations of the same word
- Search patterns must be narrow (entity_id, automation id, unique fragment) or a '/path' glob; broad topic words are rejected by the tools themselves
- secrets.yaml is excluded from searches; never claim to know its contents
- When compiling documentation, ground every statement in files you have actually read
- Ask clarifying questions if a request is ambiguous

Response Style:
- Be concise but thorough
- Use technical terms appropriately
- Format code blocks with YAML syntax
- When documenting, use clear structure with headings

Remember: You are assisting with a production Home Assistant system. Accuracy and clarity are paramount; never invent configuration you have not read."""

    # ------------------------------------------------------------------
    # Chat streaming
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Process a user message and stream response events in real time.

        The pipeline runs a multi-iteration tool-calling loop:
        1. Build the message list (system prompt, history, user message)
        2. Call the LLM in streaming mode
        3. Stream tokens to the caller as they arrive
        4. If the model requests tools, execute them and append results,
           then loop back to step 2 with the enriched context
        5. When the model produces a plain response, finish

        Args:
            user_message: The user's message/request
            conversation_history: Optional list of previous messages,
                format: [{"role": "user"|"assistant", "content": "..."}]

        Yields:
            Dict events with:
                - event: "token" | "tool_call" | "tool_start" |
                         "tool_result" | "message_complete" |
                         "complete" | "error"
                - data: JSON string with event-specific data
        """
        import json

        if not self.client:
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": "OpenAI API not configured. Please set OPENAI_API_KEY environment variable."
                })
            }
            return

        try:
            logger.info(f"Agent streaming user message: {user_message[:100]}...")

            # --- 1. Build the message list -----------------------------
            # The system prompt is the first message; with cache control
            # enabled it is marked ephemeral so providers that support
            # prompt caching reuse it across turns.
            system_message = {
                "role": "system",
                "content": self.system_prompt
            }
            if self.enable_cache_control:
                system_message["cache_control"] = {"type": "ephemeral"}
            messages = [system_message]

            # Conversation history, with a cache breakpoint on the last
            # history message once the history is substantial.
            if conversation_history:
                for idx, msg in enumerate(conversation_history):
                    is_last_history_msg = (idx == len(conversation_history) - 1)
                    if self.enable_cache_control and is_last_history_msg and len(conversation_history) >= 3:
                        msg_with_cache = dict(msg)
                        msg_with_cache["cache_control"] = {"type": "ephemeral"}
                        messages.append(msg_with_cache)
                    else:
                        messages.append(msg)

            # The current user message.
            messages.append({"role": "user", "content": user_message})

            # --- 2. Tool definitions ----------------------------------
            # Both tools are read-only. The search tool description
            # carries the narrow-pattern contract enforced server-side
            # in tools.py; keeping the descriptions in sync prevents the
            # model from making rejected calls.
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_config_files",
                        "description": (
                            "Search configuration files for a SPECIFIC identifier: an entity_id "
                            "(e.g. 'light.kitchen'), an automation/script id or unique alias "
                            "fragment, or an exact file path (prefix with '/'). Returns matching "
                            "file paths with match counts; file contents are capped in size. Never "
                            "use topic words (lighting, heating, security) or short generic terms "
                            "(light, sensor, script, yaml, on, off) - such searches will be "
                            "rejected. Devices/entities/areas are included as individual files "
                            "when the pattern matches them."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "search_pattern": {
                                    "type": "string",
                                    "description": (
                                        "Required. A narrow, specific pattern: entity_id, "
                                        "automation/script id, unique alias fragment, or "
                                        "'/path' file pattern. Must not be empty, a topic word, "
                                        "or a broad generic term."
                                    )
                                }
                            },
                            "required": ["search_pattern"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "read_config_file",
                        "description": (
                            "Read ONE configuration file by relative path (e.g. "
                            "'automations.yaml', 'scripts.yaml', 'ai_data/golem_docs_index.txt'). "
                            "Prefer this over search_config_files whenever the file is already "
                            "known. Content is capped; the 'truncated' flag shows if the file "
                            "was longer. 'lovelace.yaml' and registry entries "
                            "(devices/<id>.json, entities/<id>.json, areas/<id>.json) are also "
                            "accepted."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": (
                                        "Required. Relative path to the file (e.g. "
                                        "'configuration.yaml', 'automations.yaml')."
                                    )
                                }
                            },
                            "required": ["file_path"]
                        }
                    }
                }
            ]

            # Mark tool definitions for caching where supported.
            if self.enable_cache_control:
                for tool in tools:
                    tool["cache_control"] = {"type": "ephemeral"}

            # New messages produced during this request; returned to the
            # caller in the final 'complete' event so the UI can extend
            # its conversation history.
            new_messages = []

            # --- 3. Tool-calling loop ----------------------------------
            max_iterations = 10
            iteration = 0

            # Cumulative token usage across all iterations, reported in
            # the 'complete' event for the UI footer display.
            total_input_tokens = 0
            total_output_tokens = 0
            total_cached_tokens = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"[ITERATION {iteration}] Calling OpenAI streaming API")

                api_params = {
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": True
                }

                # Usage reporting mode as configured by the user.
                if self.usage_tracking == 'stream_options':
                    api_params["stream_options"] = {"include_usage": True}
                elif self.usage_tracking == 'usage':
                    api_params["usage"] = {"include": True}
                # 'disabled': add no usage parameters.

                if self.temperature is not None:
                    api_params["temperature"] = self.temperature

                stream = await self.client.chat.completions.create(**api_params)

                # Accumulators for this LLM call: text content and any
                # tool calls assembled from streamed deltas.
                accumulated_content = ""
                accumulated_tool_calls = []
                tool_calls_announced = False
                input_tokens = 0
                output_tokens = 0
                cached_tokens = 0

                async for chunk in stream:
                    delta = chunk.choices[0].delta

                    # Token usage arrives on the final chunk (when
                    # tracking is enabled). Multiple API formats are
                    # tolerated: OpenAI, Google and Anthropic field names.
                    if self.usage_tracking != 'disabled' and hasattr(chunk, 'usage') and chunk.usage:
                        input_tokens = getattr(chunk.usage, 'prompt_tokens', 0) or getattr(chunk.usage, 'input_tokens', 0)
                        output_tokens = getattr(chunk.usage, 'completion_tokens', 0) or getattr(chunk.usage, 'output_tokens', 0)

                        if hasattr(chunk.usage, 'cached_tokens'):
                            cached_tokens = chunk.usage.cached_tokens or 0
                        elif hasattr(chunk.usage, 'prompt_tokens_details') and chunk.usage.prompt_tokens_details:
                            cached_tokens = getattr(chunk.usage.prompt_tokens_details, 'cached_tokens', 0)
                        elif hasattr(chunk.usage, 'cached_content_token_count'):
                            cached_tokens = chunk.usage.cached_content_token_count or 0

                        logger.debug(f"[USAGE] Parsed - Input: {input_tokens}, Output: {output_tokens}, Cached: {cached_tokens}")

                        total_input_tokens += input_tokens
                        total_output_tokens += output_tokens
                        total_cached_tokens += cached_tokens

                    # Stream text tokens to the caller as they arrive.
                    if delta.content:
                        accumulated_content += delta.content
                        yield {
                            "event": "token",
                            "data": json.dumps({
                                "content": delta.content,
                                "iteration": iteration
                            })
                        }

                    # Assemble tool calls from their streamed deltas.
                    # The index field is OpenAI's format; Google omits it,
                    # so it defaults to slot 0.
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            index = tool_call_delta.index if tool_call_delta.index is not None else 0

                            while len(accumulated_tool_calls) <= index:
                                accumulated_tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })

                            current_tool_call = accumulated_tool_calls[index]
                            if tool_call_delta.id:
                                current_tool_call["id"] = tool_call_delta.id
                            if tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    current_tool_call["function"]["name"] = tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    current_tool_call["function"]["arguments"] += tool_call_delta.function.arguments

                        # Announce tool calls to the UI as soon as their
                        # names are known (arguments may still be partial).
                        if not tool_calls_announced and any(tc.get("function", {}).get("name") for tc in accumulated_tool_calls):
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "tool_calls": accumulated_tool_calls,
                                    "iteration": iteration
                                })
                            }
                            tool_calls_announced = True

                    # Stop consuming the stream once the model signals it
                    # has finished this turn.
                    if chunk.choices[0].finish_reason:
                        break

                # --- 4. Branch: plain response or tool calls ------------
                if not accumulated_tool_calls:
                    # No tool calls: this is the final answer.
                    logger.info(f"[ITERATION {iteration}] No tool calls, final response received")

                    assistant_message = {
                        "role": "assistant",
                        "content": accumulated_content
                    }
                    new_messages.append(assistant_message)

                    yield {
                        "event": "message_complete",
                        "data": json.dumps({
                            "message": assistant_message,
                            "iteration": iteration,
                            "usage": {
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "cached_tokens": cached_tokens,
                                "total_tokens": input_tokens + output_tokens
                            }
                        })
                    }
                    break

                # Tool calls present: append the assistant message to the
                # running context, then execute each tool and append its
                # result, then loop for the model's next turn.
                logger.info(f"[ITERATION {iteration}] Processing {len(accumulated_tool_calls)} tool call(s)")

                assistant_message = {
                    "role": "assistant",
                    "content": accumulated_content,
                    "tool_calls": accumulated_tool_calls
                }
                messages.append(assistant_message)
                new_messages.append(assistant_message)

                if not tool_calls_announced:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "tool_calls": accumulated_tool_calls,
                            "iteration": iteration
                        })
                    }
                    tool_calls_announced = True

                # Execute each requested tool and stream its result. The
                # dispatch table covers exactly the two read-only tools;
                # anything else is reported as unknown rather than run.
                for tool_idx, tool_call in enumerate(accumulated_tool_calls):
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])

                    logger.info(f"[ITERATION {iteration}] Calling tool: {function_name}")

                    yield {
                        "event": "tool_start",
                        "data": json.dumps({
                            "tool_call_id": tool_call["id"],
                            "function": function_name,
                            "arguments": function_args,
                            "iteration": iteration
                        })
                    }

                    if function_name == "search_config_files":
                        result = await self.tools.search_config_files(**function_args)
                    elif function_name == "read_config_file":
                        result = await self.tools.read_config_file(**function_args)
                        logger.info(f"[ITERATION {iteration}] Tool result: success={result.get('success')}, file_count={result.get('count')}")
                    else:
                        result = {
                            "success": False,
                            "error": f"Unknown tool: {function_name}. Golem exposes only read_config_file and search_config_files; both are read-only."
                        }
                        logger.error(f"[ITERATION {iteration}] Unknown tool requested: {function_name}")

                    # Append the tool result to the context. With cache
                    # control enabled the last result carries a cache
                    # breakpoint to preserve the full context window.
                    is_last_tool = (tool_idx == len(accumulated_tool_calls) - 1)
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result)
                    }
                    if self.enable_cache_control and is_last_tool:
                        tool_message["cache_control"] = {"type": "ephemeral"}

                    messages.append(tool_message)
                    new_messages.append(tool_message)

                    yield {
                        "event": "tool_result",
                        "data": json.dumps({
                            "tool_call_id": tool_call["id"],
                            "function": function_name,
                            "result": result,
                            "iteration": iteration
                        })
                    }

            # --- 5. Completion ------------------------------------------
            # If the loop exhausted its iterations the model never
            # produced a final answer; surface this as an error.
            if iteration >= max_iterations:
                logger.warning(f"Hit max iterations ({max_iterations}), stopping")
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "error": "Maximum iteration limit reached. Please try breaking down your request."
                    })
                }

            logger.info(
                f"Agent completed after {iteration} iteration(s) - Total tokens: "
                f"{total_input_tokens + total_output_tokens} (input: {total_input_tokens}, "
                f"output: {total_output_tokens}, cached: {total_cached_tokens})"
            )

            # Final event: all new messages and cumulative usage, used by
            # the front end to update history and the token footer.
            yield {
                "event": "complete",
                "data": json.dumps({
                    "messages": new_messages,
                    "iterations": iteration,
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "cached_tokens": total_cached_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens
                    }
                })
            }

        except Exception as e:
            logger.error(f"Agent streaming error: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }