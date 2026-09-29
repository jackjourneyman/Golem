# The Golem

An AI-powered assistant that helps you manage documentation for your Home Assistant

![AI Configuration Agent](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5?logo=homeassistant&logoColor=white)

---

## About

Forked from [AI Configuration Agent](https://github.com/yinzara/ha-config-ai-agent). Write access to configuration files removed. Reads .yaml and .txt files in the config folder.

## Configuration

After installation, configure the add-on with your AI provider credentials:

**Minimal Configuration (OpenAI):**
```yaml
openai_api_key: "sk-your-openai-key-here"
```

**Full Configuration:**
```yaml
openai_api_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
openai_api_key: "your-google-api-key-here"
openai_model: "gemini-2.5-flash"
log_level: "info"
system_prompt_file: ""  # Optional: Custom system prompt file path
temperature: ""  # Optional: Model temperature (0.0-2.0, empty=default)
enable_cache_control: false  # Enable prompt caching (Anthropic Claude only)
usage_tracking: "stream_options"  # Token usage method: stream_options, usage, or disabled
```

### Alternative AI Providers

<details>
<summary><b>OpenAI</b> (GPT-5, GPT-4o)</summary>

```yaml
openai_api_url: "https://api.openai.com/v1"
openai_api_key: "sk-proj-your-key-here"
openai_model: "gpt-4o"
usage_tracking: "stream_options"
```
</details>

<details>
<summary><b>Anthropic</b> (Claude)</summary>

```yaml
openai_api_url: "https://api.anthropic.com/v1/"
openai_api_key: "sk-ant-your-key"
openai_model: "claude-4-5-haiku
enable_cache_control: true
usage_tracking: "usage"
```
</details>

<details>
<summary><b>OpenRouter</b> (100+ models)</summary>

```yaml
openai_api_url: "https://openrouter.ai/api/v1"
openai_api_key: "sk-or-v1-your-key"
openai_model: "anthropic/claude-3.5-sonnet"
usage_tracking: "usage"
```
</details>
<details>
<summary><b>Local Ollama</b> (Privacy-first)</summary>

```yaml
openai_api_url: "http://ollama:11434/v1"
openai_api_key: "ollama"
openai_model: "llama3.2"
```
</details>

<details>
<summary><b>Azure OpenAI</b></summary>

```yaml
openai_api_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment"
openai_api_key: "your-azure-key"
```
</details>


<details>
<summary><b>Mistral</b> (mistral-medium-3.5)</summary>

```yaml
openai_api_url: "https://api.mistral.ai/v1/"
openai_api_key: "your-mistral-api-key"
openai_model: "mistral-medium-3.5"
usage_tracking: "stream_options"
```
</details>

### Custom System Prompt

You can customize the AI agent's behavior by providing a custom system prompt file:

1. Create a text file in your Home Assistant `/config` directory (e.g., `ai_agent_prompt.txt`)
2. Write your custom system prompt instructions
3. Set the configuration option:
   ```yaml
   system_prompt_file: "ai_agent_prompt.txt"
   ```

The file path must be relative to `/config` (e.g., `prompts/custom.txt` for `/config/prompts/custom.txt`).

If not specified or if the file is not found, the built-in default system prompt is used.

See [DOCS.md](DOCS.md) for detailed configuration options and setup instructions.

## Quick Start

1. **Install and configure** the add-on with your API key
2. **Start** the add-on
3. **Open** the "Config Agent" panel from your Home Assistant sidebar
4. **Chat** with the AI about your configuration 

## License

MIT License - See [LICENSE](../LICENSE) for details

