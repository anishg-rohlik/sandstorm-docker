/**
 * Agent runner script — executed inside the E2B sandbox.
 *
 * Uses the Claude Agent SDK's query() function directly (not the CLI).
 * Reads config from agent_config.json, streams each SDK message
 * as a JSON line to stdout.
 */
import { query } from "@anthropic-ai/claude-agent-sdk";
import { readFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(readFileSync(join(__dirname, "agent_config.json"), "utf-8"));

// Debug: Log environment and configuration
process.stderr.write(`[RUNNER DEBUG] API Key: ${process.env.ANTHROPIC_API_KEY ? 'SET (' + process.env.ANTHROPIC_API_KEY.substring(0, 15) + '...)' : 'NOT SET'}\n`);
process.stderr.write(`[RUNNER DEBUG] Auth Token: ${process.env.ANTHROPIC_AUTH_TOKEN ? 'SET (' + process.env.ANTHROPIC_AUTH_TOKEN.substring(0, 15) + '...)' : 'NOT SET'}\n`);
process.stderr.write(`[RUNNER DEBUG] Base URL: ${process.env.ANTHROPIC_BASE_URL || 'NOT SET'}\n`);
process.stderr.write(`[RUNNER DEBUG] Model: ${config.model || 'NOT SET'}\n`);
process.stderr.write(`[RUNNER DEBUG] Max Turns: ${config.max_turns || 'NOT SET'}\n`);
process.stderr.write(`[RUNNER DEBUG] Prompt: ${config.prompt.substring(0, 80)}...\n`);

const options = {
  cwd: config.cwd || "/home/user",
  permissionMode: "bypassPermissions",
  allowDangerouslySkipPermissions: true,
  // Load user-level settings (permissions, env) from ~/.claude/settings.json
  settingSources: ["user"],
};

if (config.model) options.model = config.model;
if (config.system_prompt) options.systemPrompt = config.system_prompt;
if (config.max_turns) options.maxTurns = config.max_turns;
if (config.mcp_servers) options.mcpServers = config.mcp_servers;
if (config.output_format) options.outputFormat = config.output_format;
if (config.agents) options.agents = config.agents;

process.stderr.write(`[RUNNER DEBUG] Starting query with options: ${JSON.stringify({model: options.model, maxTurns: options.maxTurns})}\n`);

try {
  process.stderr.write(`[RUNNER DEBUG] Entering query loop...\n`);
  for await (const message of query({ prompt: config.prompt, options })) {
    process.stderr.write(`[RUNNER DEBUG] Received message type: ${message.type}\n`);
    process.stdout.write(JSON.stringify(message) + "\n");

    // Break on terminal result to avoid hanging
    if (
      message.type === "result" &&
      typeof message.subtype === "string" &&
      ["success", "error_max_turns", "error_during_execution", "error_max_budget_usd", "error_max_structured_output_retries"].includes(message.subtype)
    ) {
      break;
    }
  }
} catch (err) {
  process.stdout.write(JSON.stringify({ type: "error", error: err.message }) + "\n");
  process.exit(1);
}
