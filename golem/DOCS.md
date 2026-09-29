# Home Assistant Add-on: The Golem

The Golem is an AI-powered documentation agent add-on for Home Assistant. It answers questions and compiles documentation based on what it finds in your configuration. Read-only by design: it cannot create, modify or delete anything.



---

## Installation

* Open Home Assistant and navigate to the "App Store". Click on the 3 dots (top right) and select "Repositories".

* Enter `https://github.com/jackjourneyman/Golem` in the box and click on "Add". You should now see "The Golem" at the bottom of the list.

* Click on "The Golem", then click "Install".

  


---

## Configuration

### Configuration Options

Configure the add-on through the Home Assistant UI: **Settings** → **Add-ons** → **The Golem** → **Configuration**

#### Full Configuration

```yaml
openai_api_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
openai_api_key: "your-api-key"
openai_model: "gemini-2.5-flash"
log_level: "info"
system_prompt_file: ""
temperature: ""
enable_cache_control: false
usage_tracking: "stream_options"
```

#### Configuration Parameters

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `openai_api_url` | URL | `https://generativelanguage.googleapis.com/v1beta/openai/` | API endpoint URL (Google Cloud default, can be changed to any OpenAI-compatible provider) |
| `openai_api_key` | Password | *Required* | API authentication key |
| `openai_model` | String | `gemini-2.5-flash` | Model identifier to use |
| `log_level` | List | `info` | Logging level: `debug`, `info`, `warning`, `error` |
| `system_prompt_file` | String | `""` (empty) | Optional: Path to custom system prompt file (relative to `/config`) |
| `temperature` | String | `""` (empty) | Optional: Model temperature (0.0-2.0). Lower=more focused, higher=more creative. Empty uses model default |
| `enable_cache_control` | Boolean | `false` | Enable prompt caching for Anthropic Claude models to reduce costs and improve response time |
| `usage_tracking` | List | `stream_options` | Token usage tracking method: `stream_options` (real-time), `usage` (post-response), or `disabled` |

### AI Provider Setup

The add-on supports any OpenAI-compatible API endpoint. The default configuration uses Google Cloud's Gemini API, but you can easily switch to any other provider. **Note:** Providers are adding new models all the time. Those shown here are examples only and may have been superceded.

#### Google Cloud (Default)

1. Sign up at https://aistudio.google.com/
2. Create an API key
3. The default configuration should work:
   ```yaml
   openai_api_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
   openai_api_key: "your-google-api-key"
   openai_model: "gemini-2.5-flash"
   usage_tracking: "stream_options"
   ```

#### OpenAI

1. Sign up at https://platform.openai.com/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.openai.com/v1"
   openai_api_key: "sk-proj-your-key-here"
   openai_model: "gpt-4o"
   usage_tracking: "stream_options"
   ```

#### Mistral

1. Sign up at https://console.mistral.ai/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.mistral.ai/v1/"
   openai_api_key: "your-mistral-api-key"
   openai_model: "mistral-medium-3.5"
   usage_tracking: "stream_options"
   ```

#### Anthropic

Access to the Claude family of models

1. Sign up at https://console.anthropic.com/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.anthropic.com/v1/"
   openai_api_key: "sk-ant-your-key-here"
   openai_model: "claude-sonnet-4-5"
   enable_cache_control: true
   usage_tracking: "usage"
   ```

#### OpenRouter

1. Sign up at https://openrouter.ai/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://openrouter.ai/api/v1"
   openai_api_key: "sk-or-v1-your-key"
   openai_model: "anthropic/claude-3.5-sonnet"
   usage_tracking: "usage"
   ```

#### Local Ollama

1. Install Ollama: https://ollama.ai/
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Ensure Ollama is accessible from Home Assistant
4. Configure the add-on:
   ```yaml
   openai_api_url: "http://host.docker.internal:11434/v1"
   openai_api_key: "ollama"
   openai_model: "llama3.2"
   usage_tracking: "disabled"
   ```

**Note:** Performance depends on your hardware. GPU recommended.

#### Azure OpenAI

1. Set up Azure OpenAI resource
2. Deploy a model
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2024-02-15-preview"
   openai_api_key: "your-azure-api-key"
   openai_model: "gpt-4o"
   ```

---

### Custom System Prompt

You can customize The Golem's behaviour by providing a custom system prompt file. This allows you to modify the agent's personality, instructions and focus. The prompt can direct The Golem to read curated files before scanning /config

#### Creating a Custom System Prompt

1. **Create a prompt file** in your Home Assistant `/config` directory, for example 
   
   ```
   /config/golem_prompt.txt
   ```

2. **Write your custom instructions**. One option is to start with the default prompt and modify it as needed:

<details>
<summary><b>Default System Prompt (Click to expand)</b></summary>

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

Response Style:
- Be concise but thorough
- Use technical terms appropriately
- Format code blocks with YAML syntax
- When documenting, use clear structure with headings

Remember: You are assisting with a production Home Assistant system. Accuracy and clarity are paramount; never invent configuration you have not read.
```

</details>

Here is an example of a custom prompt focused on preventing hallucinations

<details>
<summary><b>Golem Prompt (Click to expand)</b></summary>

```

0) Core principle
    It's OK to say "I don't know." Never make things up.
    When uncertain, state uncertainty plainly; avoid unjustified confidence.

1) Scope (Home Assistant, read-only)
    Inspect configuration via tools and explain findings.
    Propose changes as text only. Never execute changes or call HA services.
    Answer directly and concisely. No unrelated information.

2) Evidence rules (no invented entities; cite everything)
    Base answers on evidence (local docs/config) and clear reasoning,
    not on user preference.

    Citation requirement (mandatory):
    - Every factual claim must name the source that supports it: the file
      read and the item within it (entity, automation, script, template,
      label).
    - Claims supported only by a user's assertion, by a name-based
      inference, or by an incomplete read must be labelled "unverified".
    - If you cannot name a source for a claim, do not make the claim. Say
      what you looked for, where you looked, and that it was not found.

    Entity rules:
    - Only mention entities/devices/areas that exist in configuration you
      have read, or that the user explicitly provided. Treat user-provided
      entity_ids as hypothetical until confirmed in config.
    - Do not infer purpose from names alone; use domain/type/config
      evidence.
    - If key information is missing, ask one targeted follow-up question
      (or offer 1-3 labelled hypotheses, each marked unverified).

    Incomplete reads:
    - If you read only part of a file, say so and state which parts.

3) Source priority
    Priority order: tool limits > read-only bounds > local docs (intended
    behaviour) > local config (actual behaviour) > general HA knowledge.
    Treat runtime state as "reality" only when accessible via tools;
    otherwise say so and rely on docs/config. Treat unknown/unavailable
    states as uncertainty.

4) File and tool usage (minimise reads and tokens)
    Tool paths are relative to /config (e.g. 'ai_data/golem_docs_index.txt').

    Reading a known file (default first step):
    - Use read_config_file with the exact relative path.
    - First read ai_data/golem_docs_index.txt (table of contents), then the
      specific curated docs/summaries it lists, as relevant.```
    - read_config_file returns at most 8000 characters; if 'truncated' is
      true, say so and read the remainder only if needed.

    Searching:
    - Use search_config_files ONLY for a specific identifier: an
      entity_id, an automation/script id, or a unique alias fragment.
    - Never use topic words or broad terms; the tool rejects them.
    - If the user's question contains no specific identifier, do not
      search. Answer from curated docs, or ask one clarifying question
      requesting a specific identifier.

    Topic questions ("tell me about X", "provide information about X"):
    - Answer only from curated docs and summaries in ai_data/*
      (e.g., the policy file for the topic).
    - Never search or read raw YAML for a topic question; raw config is
      for specific named items only.
    - If the curated docs do not cover the topic, say so.

    Allowlist (default-deny):```
    - Always allowed: anything under ai_data/*.
    - Raw config, only when the discussion is about a specific item:
      configuration.yaml, automations.yaml, scripts.yaml, templates.yaml,
      binary_sensors.yaml, intents.yaml, watchman_report.txt.
    - Anything else: read only if the user names the file exactly.
    - Before using generated summaries, check ai_data/last_update.yaml;
      warn if older than 7 days.

    Context limit (hard rule):
    - Do not open many files "just in case".
    - If the next read may exceed remaining context, stop. Report what
      was read and what remains unresolved, and ask the user for a
      narrower target. Never retry a failed oversized read.

5) Documentation and drift workflow (for "why/how/document" questions)
    Read the index first. Use policies for intended behaviour and the
    generated summaries to identify the implementing items. Open raw YAML
    only for those items.
    If intent and config disagree, report the mismatch explicitly.
    If the answer depends on state, logs, traces, or history not accessible
    via tools, say so and request the specific artifact.
    Default System</details>
6) Identity and tone
    You are The Golem: a quiet, neutral librarian for the Home Assistant
    system.
    Professional; no motivational tone. Correct errors plainly; do not
    agree just to be polite.
```

</details>

3. **Configure the add-on** to use your custom prompt:

```yaml
   system_prompt_file: "golem_prompt.txt"
```

4. **Restart the add-on** to load the new prompt

#### File Path Requirements

- Paths must be **relative** to `/config`
- Security: Path traversal is blocked (cannot access files outside `/config`)
- Examples:
  - `golem_prompt.txt` → `/config/golem_prompt.txt`
  - `prompts/custom.txt` → `/config/prompts/custom.txt`
  - `ai/system_prompt.md` → `/config/ai/system_prompt.md`

#### Fallback Behavior

- If `system_prompt_file` is empty or not set, the built-in default prompt is used
- If the specified file is not found, a warning is logged and the default prompt is used
- If there is an error reading the file, the default prompt is used

#### Tips for Custom Prompts

**Structure your prompt with:**
- Clear role definition
- Key responsibilities
- Important guidelines and constraints
- Response style preferences

**Example use cases:**
- Focus on specific integrations (e.g., "You specialize in Zigbee and Z-Wave configurations")
- Emphasize documentation style and structure
- Customize personality and tone
- Reference curated files in `/config` (e.g., "Read lighting_policy.txt before answering lighting questions")

**Note:** The system prompt significantly affects the agent's behaviour. Test changes carefully. If your custom prompt removes the read-only instruction, the agent may still decline to change configuration - the tools themselves are read-only - but it may spend effort attempting calls that will fail.

### Temperature Configuration

The `temperature` parameter controls the randomness and creativity of AI responses:

- **Range:** 0.0 to 2.0
- **Lower values (0.0-0.7):** More focused, deterministic, and consistent responses. Recommended for configuration analysis and documentation.
- **Medium values (0.7-1.0):** Balanced between creativity and consistency.
- **Higher values (1.0-2.0):** More creative and varied responses. May be less predictable.
- **Empty/Default:** Uses the model's default temperature setting.

**Example configurations:**
```yaml
temperature: ""        # Use model default
temperature: "0.5"     # Conservative, consistent (recommended)
temperature: "1.0"     # Balanced
temperature: "1.5"     # More creative
```

**Note:** Not all models support custom temperature settings. Check your provider's documentation.

### Prompt Caching (Anthropic Claude Only)

The `enable_cache_control` option enables prompt caching for Anthropic Claude models, which can significantly reduce costs and improve response times for repeated conversations.

**How it works:**
- The system prompt is marked as cacheable
- Claude caches the prompt for 5 minutes
- Subsequent requests within 5 minutes reuse the cached prompt
- Reduces input token costs by ~90% for cached content

**Configuration:**
```yaml
enable_cache_control: true   # Enable for Anthropic Claude models
enable_cache_control: false  # Disable for all other providers (default)
```

**Important:** Only set to `true` when using **Anthropic Claude models** (claude-4-5-sonnet, etc.). This feature will cause errors or be ignored by other providers like OpenAI, Google, Mistral, or OpenRouter with non-Anthropic models.

**When to enable:**
- Using direct Anthropic API with Claude models
- Using OpenRouter with Anthropic Claude models

**When NOT to enable:**

- Using OpenAI, Google Gemini, Mistral, or other providers
- Using OpenRouter with non-Anthropic models

### Token Usage Tracking

The `usage_tracking` option controls how token usage statistics are collected and displayed in the footer.

**Options:**

1. **`stream_options`** (Real-time tracking)
   - Token counts update live during streaming responses
   - Shows cumulative input/output/cached tokens as messages arrive
   - Best user experience with immediate feedback
   - **Use for:** OpenAI, Google Gemini and Mistral

2. **`usage`** (Post-response tracking)
   - Token counts reported after the full response completes
   - Uses the standard `usage` field in API responses
   - Slightly delayed display compared to streaming
   - **Use for:** Anthropic Claude and OpenRouter

3. **`disabled`** (No tracking)
   - Token counting completely disabled
   - Footer token statistics won't be displayed
   - **Use for:** Local models (Ollama) or when tracking isn't needed/supported

**Configuration by Provider:**

```yaml
# OpenAI
usage_tracking: "stream_options"  # Recommended

# Google Gemini
usage_tracking: "stream_options"  # Recommended

# Mistral
usage_tracking: "stream_options"  # Recommended

# Anthropic Claude (direct API)
usage_tracking: "usage"           # Recommended

# OpenRouter (any model)
usage_tracking: "usage"           # Recommended (safer compatibility)
# OR
usage_tracking: "disabled"        # If experiencing errors

# Local Ollama
usage_tracking: "disabled"        # Doesn't report usage
```

**Important Notes:**

- **OpenRouter:** Some models may not support either tracking method reliably. If you experience errors or missing token counts, use `disabled`.

- **`stream_options` errors:** If a model doesn't support `stream_options`, it may cause streaming failures. Switch to `usage` or `disabled` if this occurs.

  

---

## Usage

Open The Golem from the Home Assistant sidebar and ask questions in plain language. The agent reads your configuration and answers with references to the actual files.



### What Golem Can Do

- **Answer questions** about automations, scripts, dashboards, entities, devices and areas
- **Explain behaviour** - why an automation triggers, how entities relate to devices and areas
- **Compile documentation** for the whole instance or a specific integration, grounded in the files it has read
- **Read curated files** you place in `/config` (policies, notes, indexes) and use them when answering
- **Show configuration** excerpts with correct YAML formatting

### What Golem Cannot Do

- Create, modify or delete any file in `/config`
- Rename devices, entities or areas, or modify the dashboard
- Reload or restart Home Assistant services

When you ask for a change, Golem will tell you it is read-only and instead explain the YAML you would need to alter and how.

### How It Reads Your Configuration

- **File searches** require a narrow, specific identifier (an entity_id, an automation id, a unique fragment) or a file path glob; broad topic words are rejected to protect the context window

- **`secrets.yaml` is always excluded** - its contents are never sent to the AI provider

- **`custom_components` are skipped** - third-party code is not your configuration

- **Registries and the dashboard** are read via the Home Assistant WebSocket API, since they live in the database rather than in files

  

---

## Read-Only Design

The Golem is a fork of a configuration-editing agent, with all write capability deliberately removed at multiple layers:

1. **Volume mappings** - the Home Assistant configuration is mounted `read_only: true`
2. **AppArmor** - the profile permits read access only to the configuration directory
3. **No write code** - the agent's tools are limited to `read_config_file` and `search_config_files`; the write and approval pipeline from the parent project has been deleted
4. **WebSocket client** - only read commands (registries, dashboard) remain

---

See [README.md](README.md) for a summary and [CHANGELOG.md](CHANGELOG.md) for version history.