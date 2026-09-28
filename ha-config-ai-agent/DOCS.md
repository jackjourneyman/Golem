# The Golem - Documentation

Complete guide for installing, configuring, and using the AI Documentation Agent add-on for Home Assistant.

## Table of Contents

- [Installation](#installation)
  - [Manual Installation](#manual-installation)
  - [Local Development](#local-development)
  
- [Configuration](#configuration)
  - [Configuration Options](#configuration-options)
  
  - [AI Provider Setup](#ai-provider-setup)
  
    

---

## Installation

### Manual Installation

The Golem is installed as a local Home Assistant add-on.

#### Prerequisites
- Home Assistant OS or Supervised installation
- Access to the Home Assistant file system
- An OpenAI API key (or compatible provider)

#### Local Installation Steps

1. **Access your Home Assistant configuration directory**
   - Via SSH, Samba share, or Terminal add-on

2. **Create the addons directory** (if it doesn't exist)
   ```bash
   mkdir -p /config/addons
   cd /config/addons
   ```

3. **Clone the repository**
   ```bash
   git clone https://github.com/jackjourneyman/Golem.git
   ```

4. **Add the local repository in Home Assistant**
   - Navigate to **Settings** → **Add-ons** → **Add-on Store**
   - Click the menu icon (⋮) in the top right
   - Select **Repositories**
   - Add `/addons` as a repository
   - Click **Add** then **Close**

5. **Install the add-on**
   - Refresh the Add-on Store page
   - Find "The Golem" in the local add-ons section
   - Click on it and press **Install**
   - Wait for the installation to complete

6. **Configure the add-on**
   - See [Configuration](#configuration) section below

7. **Start the add-on**
   - Click **Start** on the add-on page
   - Optionally enable **Start on boot** and **Watchdog**

8. **Access the interface**
   - Click **Open Web UI** or
   - Find "Documentation Agent" in your Home Assistant sidebar

---

## Configuration

### Configuration Options

Configure the add-on through the Home Assistant UI: **Settings** → **Add-ons** → **The Golem** → **Configuration**

#### Basic Configuration

```yaml
openai_api_key: "sk-your-openai-api-key"
```

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

The add-on supports any OpenAI-compatible API endpoint. The default configuration uses Google Cloud's Gemini API, but you can easily switch to any other provider.

#### Google Cloud (Default)

**Best for:** Fast responses, cost-effective, high quality

The add-on is configured by default to use Google Cloud's Gemini API.

1. Sign up at https://aistudio.google.com/
2. Create an API key
3. The default configuration should work:
   ```yaml
   openai_api_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
   openai_api_key: "your-google-api-key"
   openai_model: "gemini-2.5-flash"
   usage_tracking: "stream_options"
   ```

**Recommended models:**
- `gemini-2.5-flash` - Default, best balance of speed and quality
- `gemini-2.0-flash-exp` - Experimental, cutting-edge features
- `gemini-2.5-pro` - Higher quality, longer context
- `gemini-1.5-flash` - Faster, lower cost

#### OpenAI

**Best for:** Production use, proven reliability

1. Sign up at https://platform.openai.com/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.openai.com/v1"
   openai_api_key: "sk-proj-your-key-here"
   openai_model: "gpt-4o"
   usage_tracking: "stream_options"
   ```

**Recommended models:**
- `gpt-5-mini` - Best seed and cost but requires validation
- `gpt-4o` - Best balance of speed and quality without validation
- `gpt-4o-mini` - Faster, lower cost
- `gpt-5` - Advanced reasoning (slower, more expensive)

#### OpenRouter

**Best for:** Access to multiple models, competitive pricing

1. Sign up at https://openrouter.ai/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://openrouter.ai/api/v1"
   openai_api_key: "sk-or-v1-your-key"
   openai_model: "anthropic/claude-3.5-sonnet"
   ```

#### Anthropic

Access to the Claude family of models

1. Sign up at https://console.anthropic.com/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.anthropic.com/v1/"
   openai_api_key: "sk-or-v1-your-key"
   openai_model: "claude-sonnet-4-5"
   ```

**Recommended models:**
- `claude-4.5-haiku` - Fast inexpensive reasoning
- `claude-4.5-sonnet` - Excellent reasoning


#### Local Ollama

**Best for:** Privacy, offline use, no API costs

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
   ```

**Recommended models:**
- `llama3.2` - Good general performance
- `mistral` - Fast and capable
- `codellama` - Optimized for code

**Note:** Performance depends on your hardware. GPU recommended.

### Custom System Prompt

You can customize The Golem's behavior by providing a custom system prompt file. This allows you to modify the agent's personality, instructions, and capabilities without modifying the add-on code.

#### Creating a Custom System Prompt

1. **Create a prompt file** in your Home Assistant `/config` directory:
   ```bash
   # Example: Create a file at /config/ai_agent_prompt.txt
   nano /config/ai_agent_prompt.txt
   ```

2. **Write your custom instructions**. Start with the default prompt and modify as needed:

<details>
<summary><b>Default System Prompt (Click to expand)</b></summary>

```text
You are a Home Assistant Configuration Assistant.

Your role is to help users manage their Home Assistant configuration files safely and effectively.

Key Responsibilities:
1. **Understanding Requests**: Interpret user requests about Home Assistant configuration
2. **Reading Configuration**: Use tools to examine current configuration files
3. **Proposing Changes**: Suggest configuration changes with clear explanations using the propose_config_changes tool without requesting confirmation
4. **Safety First**: Always explain the impact of changes before proposing them
5. **Best Practices**: Guide users toward Home Assistant best practices

Available Tools:
- search_config_files: Search for terms in configuration (use first)
- propose_config_changes: Propose changes for user approval

Important Guidelines:
- NEVER suggest changes directly - always use propose_config_change
- Explain your reasoning in your response when calling propose_config_changes
- The user can accept or reject your proposed config changes through their own UI
- Explain WHY you're proposing changes, not just WHAT
- Preserve all existing code, comments and structure when possible
- Only change what's needed to complete the request of the user
- Validate that changes align with Home Assistant documentation
- Warn users about potential breaking changes
- Suggest testing in a development environment for major changes
- Remember when searching for files that terms are case-insensitive so don't search for multiple case variations of a word

Response Style:
- Be concise but thorough
- Use technical terms appropriately
- Provide examples when helpful
- Format code blocks with YAML syntax
- Ask clarifying questions if request is ambiguous

Remember: You're helping manage a production Home Assistant system. Safety and clarity are paramount.
```

</details>

3. **Configure the add-on** to use your custom prompt:
   ```yaml
   system_prompt_file: "ai_agent_prompt.txt"
   ```

4. **Restart the add-on** to load the new prompt

#### File Path Requirements

- Path must be **relative** to `/config`
- Security: Path traversal is blocked (cannot access files outside `/config`)
- Examples:
  - `ai_agent_prompt.txt` → `/config/ai_agent_prompt.txt`
  - `prompts/custom.txt` → `/config/prompts/custom.txt`
  - `ai/system_prompt.md` → `/config/ai/system_prompt.md`

#### Fallback Behavior

- If `system_prompt_file` is empty or not set, the built-in default prompt is used
- If the specified file is not found, a warning is logged and the default prompt is used
- If there's an error reading the file, the default prompt is used

### Temperature Configuration

The `temperature` parameter controls the randomness and creativity of AI responses:

- **Range:** 0.0 to 2.0
- **Lower values (0.0-0.7):** More focused, deterministic, and consistent responses. Recommended for configuration management.
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

**⚠️ Important:** Only set to `true` when using **Anthropic Claude models** (claude-3-5-sonnet, claude-4-sonnet, etc.). This feature will cause errors or be ignored by other providers like OpenAI, Google, or OpenRouter with non-Anthropic models.

**When to enable:**
- ✅ Using direct Anthropic API with Claude models
- ✅ Using OpenRouter with Anthropic Claude models
- ❌ Using OpenAI, Google Gemini, or other providers
- ❌ Using OpenRouter with non-Anthropic models

### Token Usage Tracking

The `usage_tracking` option controls how token usage statistics are collected and displayed in the footer.

**Options:**

1. **`stream_options`** (Real-time tracking)
   - Token counts update live during streaming responses
   - Shows cumulative input/output/cached tokens as messages arrive
   - Best user experience with immediate feedback
   - **Use for:** OpenAI (GPT-4, GPT-5, etc.) and Google Gemini

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
# OpenAI (GPT-4, GPT-5, etc.)
usage_tracking: "stream_options"  # ✅ Recommended

# Google Gemini
usage_tracking: "stream_options"  # ✅ Recommended

# Anthropic Claude (direct API)
usage_tracking: "usage"           # ✅ Recommended

# OpenRouter (any model)
usage_tracking: "usage"           # ✅ Recommended (safer compatibility)
# OR
usage_tracking: "disabled"        # ✅ If experiencing errors

# Local Ollama
usage_tracking: "disabled"        # ✅ Doesn't report usage
```

**⚠️ Important Notes:**
- **OpenRouter:** Some models may not support either tracking method reliably. If you experience errors or missing token counts, use `disabled`.
- **`stream_options` errors:** If a model doesn't support `stream_options`, it may cause streaming failures. Switch to `usage` or `disabled` if this occurs.
- **Anthropic with `stream_options`:** While technically supported, `usage` is more reliable for Claude models through OpenRouter.

#### Tips for Custom Prompts

**Structure your prompt with:**
- Clear role definition
- Key responsibilities
- Available tools (search_config_files, propose_config_changes)
- Important guidelines and constraints
- Response style preferences

**Example use cases:**
- Focus on specific integrations (e.g., "You specialize in Zigbee and Z-Wave configurations")
- Emphasize automation best practices
- Add domain-specific knowledge (e.g., "You understand solar energy systems")
- Customize personality and tone
- Add custom validation rules

**Note:** The system prompt significantly affects the agent's behavior. Test changes carefully.

#### Azure OpenAI

**Best for:** Enterprise deployments, compliance requirements

1. Set up Azure OpenAI resource
2. Deploy a model
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2024-02-15-preview"
   openai_api_key: "your-azure-api-key"
   openai_model: "gpt-5-mini"
   ```

---

