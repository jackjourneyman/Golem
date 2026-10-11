# Home Assistant Add-on: The Golem

The Golem is an AI-powered documentation agent add-on for Home Assistant. It answers questions and compiles documentation based on what it finds in your configuration. Read-only by design: it cannot create, modify or delete anything.

This document describes version 0.6.1. See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## Installation

1. Open Home Assistant and navigate to **Settings** → **Add-ons** → **Add-on Store**.
2. Click the menu icon (three dots, top right) and select **Repositories**.
3. Enter `https://github.com/jackjourneyman/Golem` and click **Add**.
4. Return to the Add-on Store, find **The Golem** at the bottom of the list, open it and click **Install**.
5. Configure the add-on (see below) and start it.

---

## Configuration

Configure the add-on through the Home Assistant UI: **Settings** → **Add-ons** → **The Golem** → **Configuration**.

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `openai_api_url` | URL | `https://generativelanguage.googleapis.com/v1beta/openai/` | API endpoint URL of any OpenAI-compatible provider |
| `openai_api_key` | Password | *(required)* | API authentication key |
| `openai_model` | String | `gemini-2.5-flash` | Model identifier to use |
| `log_level` | List | `info` | Logging level: `debug`, `info`, `warning`, `error` |
| `system_prompt_file` | String | `""` (empty) | Optional: path to a custom system prompt file, relative to `/config` |
| `temperature` | String | `""` (empty) | Optional: model temperature (0.0–2.0). Empty uses the provider default |
| `enable_cache_control` | Boolean | `false` | Mark prompts for provider-side caching (see below) |
| `usage_tracking` | List | `stream_options` | Token usage reporting method: `stream_options`, `usage` or `disabled` |

> **Note on the defaults.** The default URL and model (`generativelanguage.googleapis.com` / `gemini-2.5-flash`) are inherited from the parent project, [AI Configuration Agent](https://github.com/yinzara/ha-config-ai-agent). The Golem talks to any endpoint that implements the OpenAI chat-completions API, but the add-on maintainer has only verified it in use with **OpenAI's GPT models** and with **Mistral models**. Configuration of other providers is described below for completeness, but is untested with this add-on.

### AI Provider Setup

#### OpenAI (tested)

1. Sign up at https://platform.openai.com/ and create an API key.
2. Configure the add-on:

```yaml
openai_api_url: "https://api.openai.com/v1"
openai_api_key: "sk-proj-your-key-here"
openai_model: "gpt-4o"
usage_tracking: "stream_options"
```

Model identifiers change as providers release new models; check the provider's documentation for the current list.

#### Mistral (tested)

1. Sign up at https://console.mistral.ai/ and create an API key.
2. Configure the add-on:

```yaml
openai_api_url: "https://api.mistral.ai/v1/"
openai_api_key: "your-mistral-api-key"
openai_model: "mistral-medium-3.5"
usage_tracking: "stream_options"
```

#### Other OpenAI-compatible providers (untested)

The add-on only requires an OpenAI-compatible chat-completions endpoint, so other providers should work, but the following configurations have **not** been verified with The Golem and are offered without warranty:

```yaml
# Google Gemini (the inherited default)
openai_api_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
openai_model: "gemini-2.5-flash"

# Anthropic Claude
openai_api_url: "https://api.anthropic.com/v1/"
openai_model: "claude-sonnet-4-5"
enable_cache_control: true
usage_tracking: "usage"

# OpenRouter
openai_api_url: "https://openrouter.ai/api/v1"
openai_model: "anthropic/claude-3.5-sonnet"
usage_tracking: "usage"

# Local Ollama
openai_api_url: "http://host.docker.internal:11434/v1"
openai_api_key: "ollama"
openai_model: "llama3.2"
usage_tracking: "disabled"

# Azure OpenAI
openai_api_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2024-02-15-preview"
openai_model: "gpt-4o"
```

### Temperature

The `temperature` parameter controls the randomness of AI responses:

- **0.0–0.7:** more focused and consistent responses. Recommended for configuration analysis and documentation.
- **0.7–1.0:** a balance between consistency and variety.
- **1.0–2.0:** more varied, less predictable responses; generally not useful here.
- **Empty:** the provider's default temperature is used.

```yaml
temperature: ""     # provider default
temperature: "0.5"  # conservative, recommended
```

Not all models support a custom temperature; check your provider's documentation.

### Prompt Caching

`enable_cache_control` marks the system prompt (and later messages) with a cache-control annotation, which providers that support prompt caching may use to reduce the cost and latency of repeated conversations. This feature is inherited from the parent project, where it targeted Anthropic Claude models; **it is untested with The Golem**. Leave it `false` unless you know your provider supports this annotation, as other providers may reject it.

### Token Usage Tracking

`usage_tracking` controls how token usage statistics are collected and displayed in the chat footer:

- **`stream_options`** (default): requests usage with the OpenAI `stream_options.include_usage` parameter. Use this with OpenAI and Mistral.
- **`usage`**: requests usage with the alternative `usage.include` format. Try this if your provider does not support `stream_options`.
- **`disabled`**: no usage parameters are sent; the footer shows no statistics. Use this if a provider rejects both of the above, or if you do not want usage reported.

---

## Custom System Prompt

You can customize The Golem's behaviour by providing a custom system prompt file. This is also the supported way to teach The Golem about curated documentation files you maintain in `/config` (see below).

#### Creating a Custom System Prompt

1. Create a prompt file in your Home Assistant `/config` directory, for example:

   ```
   /config/golem_prompt.txt
   ```

2. Write your custom instructions. One option is to start with the default prompt (below) and modify it.

3. Configure the add-on to use it:

   ```yaml
   system_prompt_file: "golem_prompt.txt"
   ```

4. Restart the add-on to load the new prompt.

#### File Path Requirements

- Paths are relative to `/config` (for example `prompts/custom.txt` resolves to `/config/prompts/custom.txt`).
- Path traversal is blocked: files outside `/config` cannot be referenced.

#### Fallback Behaviour

- If `system_prompt_file` is empty or not set, the built-in default prompt is used.
- If the specified file is not found, or cannot be read, a warning is logged and the default prompt is used.

#### Default System Prompt

The built-in default prompt (as of 0.6.0) is reproduced here so it can be used as a starting point:

<details>
<summary><b>Default System Prompt (click to expand)</b></summary>

```text
You are Golem, a read-only Home Assistant documentation and question-answering assistant.

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
- Reading large files: if a read returns truncated=true and the user explicitly named that file, either re-read it with full_read=true, or read it in sequential chunks with offset/length (continue at next_offset until has_more is false). Do not answer questions that require the whole file until you have read all of it; if a full read is refused as too large, complete the task with chunked passes. State plainly if any part could not be read.

Response Style:
- Be concise but thorough
- Use technical terms appropriately
- Format code blocks with YAML syntax
- When documenting, use clear structure with headings

Remember: You are assisting with a production Home Assistant system. Accuracy and clarity are paramount; never invent configuration you have not read.
```

</details>

#### Curated Files

The Golem can read curated documentation, policy files and indexes that you maintain anywhere under `/config` (for example a documentation index in an `ai_data/` directory). Since 0.5.3 the agent does not assume that any particular curated file exists, and will ask you for the exact path when it is unsure. If you keep curated files, name them in a custom system prompt — for example by adding a paragraph such as:

```text
Before answering broad questions, read the documentation index at
ai_data/index.txt and consult the curated documents it lists.
```

#### Tips for Custom Prompts

Structure your prompt around: role definition, key responsibilities, guidelines and constraints, and response style. The system prompt significantly affects the agent's behaviour; test changes carefully. If a custom prompt removes the read-only instruction, the agent may spend effort attempting calls that will fail — the tools themselves remain read-only in any case.

---

## Usage

Open The Golem from the Home Assistant sidebar and ask questions in plain language. The agent reads your configuration and answers with references to the actual files. Chats persist between sessions; use the New chat button to start a fresh conversation.

### What Golem Can Do

- Answer questions about automations, scripts, dashboards, entities, devices and areas
- Explain behaviour: why an automation triggers, how entities relate to devices and areas
- Compile documentation for the whole instance or a specific integration, grounded in the files it has read
- Read curated files you place in `/config` (policies, notes, indexes) and use them when answering, provided they are introduced in the system prompt
- Show configuration excerpts with correct YAML formatting

### What Golem Cannot Do

- Create, modify or delete any file in `/config`
- Rename devices, entities or areas, or modify the dashboard
- Reload or restart Home Assistant services

When you ask for a change, The Golem will state that it is read-only and instead explain the YAML you would need to alter and how.

### How It Reads Your Configuration

The Golem exposes two tools to the model, both read-only and both bounded so that a single response can never flood the model's context window:

- **`search_config_files`**: search all YAML and `.txt` files for a narrow, specific identifier — an entity_id, an automation/script id, or a unique fragment — or a file path glob (a pattern starting with `/`). Broad topic words (for example `lighting`, `sensor`, `automation`) and patterns shorter than four characters are rejected by the tools themselves.
- **`read_config_file`**: read one known file by its relative path.

#### Read Limits

| Bound | Value |
|-------|-------|
| Default cap per direct file read | 60,000 characters |
| Cap per file within search results | 8,000 characters |
| Maximum files returned per search | 20 |
| Hard ceiling for a one-pass full read (`full_read: true`) | 400,000 characters |
| Default chunk size for paged reads (`offset`/`length`) | 60,000 characters |

Since 0.6.0, large files can be read whole or in sequential passes: a truncated default read reports the file's total length and how to obtain the remainder; the model may re-read an explicitly named file with `full_read`, or page through it in chunks using `offset` and `length` until the end of the file is reached.

#### Exclusions and Virtual Files

- **`secrets.yaml` is always excluded** — its contents are never sent to the AI provider.
- **`custom_components` are skipped** — third-party code is not your configuration.
- **Registries and the dashboard** live in the Home Assistant database rather than in files, so they are read through the WebSocket API and presented to the model as virtual files: `lovelace.yaml` (the dashboard), `devices/<id>.json`, `entities/<id>.json` and `areas/<id>.json`.

---

## Read-Only Design

The Golem is a fork of a configuration-editing agent, with all write capability deliberately removed at multiple layers:

1. **Volume mappings** — the Home Assistant configuration is mounted `read_only: true`
2. **AppArmor** — the profile permits read access only to the configuration directory
3. **No write code** — the agent's tools are limited to `read_config_file` and `search_config_files`; the write and approval pipeline from the parent project has been deleted
4. **WebSocket client** — only read commands (registries, dashboard) remain

---

See [README.md](README.md) for a summary and [CHANGELOG.md](CHANGELOG.md) for version history.