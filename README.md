This is the repository for the Home Assistant Golem add-on.

An AI-powered Home Assistant configuration assistant with approval workflow.

**Chat with your configuration:**
- "Enable debug logging for the MQTT integration"
- "Show me all my automations that involve lights"
- "Rename my 'Office Button' device to 'Desk Button'"
- "Create an automation that turns on the porch light at sunset"

# Installation

## Option 1: HACS Custom Component (Recommended for Core/Container)

1. **Add to HACS:**
   - Open HACS → Integrations
   - Click ⋮ → Custom repositories
   - Add: `https://github.com/yinzara/ha-config-ai-agent`
   - Category: Integration

2. **Install:**
   - Search for "AI Configuration Agent"
   - Click Download
   - Restart Home Assistant

3. **Configure:**
   - Settings → Devices & Services → Add Integration
   - Search "AI Configuration Agent"
   - Enter API key and settings

## Option 2: Home Assistant Add-on (Supervisor Required)

1. Navigate to Settings → Add-ons → Add-on Store
2. Click ⋮ → Repositories
3. Add: `https://github.com/jackjourneyman/Golem'
4. Find "The Golem" and click Install
5. Configure and Start

# Features
* 🤖 **Natural Language Interface** - No YAML expertise required
* ✅ **Approval Workflow** - Review visual diffs before applying changes
* 🔒 **Safe Operations** - Automatic backups, validation, and rollback
* 📊 **Visual Diffs** - See exactly what will change
* 🔌 **Flexible AI Providers** - OpenAI, OpenRouter, Ollama, Azure, or any OpenAI-compatible API
* 📝 **Configuration Management** - Automations, scripts, Lovelace, devices, entities, and areas
* 🔄 **Auto-Reload** - Home Assistant configuration reloads automatically after changes
