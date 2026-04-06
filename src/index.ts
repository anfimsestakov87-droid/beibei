#!/usr/bin/env node
/**
 * Telegram MCP Server
 *
 * Provides tools for sending messages and media to Telegram chats/channels
 * via the Telegram Bot API. Designed for remote deployment with HTTP transport.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express from "express";
import axios, { AxiosError } from "axios";
import { z } from "zod";

// ─── Config ────────────────────────────────────────────────────────────────

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const PORT = parseInt(process.env.PORT || "3000");
const API_BASE = `https://api.telegram.org/bot${BOT_TOKEN}`;

// ─── Telegram API helper ────────────────────────────────────────────────────

interface TelegramResponse<T> {
  ok: boolean;
  result?: T;
  description?: string;
}

async function telegramCall<T>(
  method: string,
  body: Record<string, unknown>
): Promise<T> {
  try {
    const res = await axios.post<TelegramResponse<T>>(
      `${API_BASE}/${method}`,
      body,
      { timeout: 30000, headers: { "Content-Type": "application/json" } }
    );
    if (!res.data.ok) {
      throw new Error(res.data.description ?? "Telegram API error");
    }
    return res.data.result as T;
  } catch (error) {
    if (error instanceof AxiosError && error.response) {
      const desc = (error.response.data as TelegramResponse<unknown>).description;
      throw new Error(desc ?? `HTTP ${error.response.status}`);
    }
    throw error;
  }
}

function apiError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message.includes("chat not found")) {
      return "Error: Chat not found. Make sure the bot is added to the chat and the chat_id is correct.";
    }
    if (error.message.includes("bot was kicked")) {
      return "Error: Bot was kicked from the chat. Re-add the bot first.";
    }
    if (error.message.includes("not enough rights")) {
      return "Error: Bot does not have permission to post in this chat.";
    }
    return `Error: ${error.message}`;
  }
  return `Error: ${String(error)}`;
}

// ─── MCP Server ────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "telegram-mcp-server",
  version: "1.0.0",
});

// Tool: send_message
server.registerTool(
  "telegram_send_message",
  {
    title: "Send Telegram Message",
    description: `Send a text message to a Telegram chat or channel.

Supports Markdown and HTML formatting. Use this for text-only posts such as
weekly rankings, match previews, game guides, and general announcements.

Args:
  - chat_id (string): Target chat ID or @username (e.g. "-1001234567890" or "@mychannel")
  - text (string): Message content (max 4096 characters)
  - parse_mode (string, optional): "Markdown" | "HTML" | "" — default "Markdown"
  - disable_notification (boolean, optional): Send silently — default false

Returns:
  JSON with message_id and chat details on success.`,
    inputSchema: z.object({
      chat_id: z.string().describe("Chat ID or @username of the target chat"),
      text: z.string().min(1).max(4096).describe("Message text to send"),
      parse_mode: z
        .enum(["Markdown", "HTML", ""])
        .default("Markdown")
        .describe('Formatting mode: "Markdown", "HTML", or "" for plain text'),
      disable_notification: z
        .boolean()
        .default(false)
        .describe("If true, sends the message silently"),
    }),
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: true,
    },
  },
  async ({ chat_id, text, parse_mode, disable_notification }) => {
    try {
      const body: Record<string, unknown> = {
        chat_id,
        text,
        disable_notification,
      };
      if (parse_mode) body.parse_mode = parse_mode;

      const result = await telegramCall<{
        message_id: number;
        chat: { id: number; title?: string; username?: string };
      }>("sendMessage", body);

      const output = {
        success: true,
        message_id: result.message_id,
        chat_id: result.chat.id,
        chat_title: result.chat.title ?? result.chat.username ?? String(result.chat.id),
      };
      return {
        content: [{ type: "text", text: JSON.stringify(output, null, 2) }],
        structuredContent: output,
      };
    } catch (error) {
      return { content: [{ type: "text", text: apiError(error) }] };
    }
  }
);

// Tool: send_photo
server.registerTool(
  "telegram_send_photo",
  {
    title: "Send Telegram Photo",
    description: `Send a photo to a Telegram chat or channel, with an optional caption.

Use this for game guide banners, promo images, match previews with visuals,
and any content that requires an image. Photo can be a public URL or a file_id.

Args:
  - chat_id (string): Target chat ID or @username
  - photo (string): Public HTTPS URL or Telegram file_id of the image
  - caption (string, optional): Caption text shown below the photo (max 1024 chars)
  - parse_mode (string, optional): "Markdown" | "HTML" | "" — default "Markdown"
  - disable_notification (boolean, optional): Send silently — default false

Returns:
  JSON with message_id on success.`,
    inputSchema: z.object({
      chat_id: z.string().describe("Chat ID or @username"),
      photo: z
        .string()
        .describe("Public HTTPS URL or Telegram file_id of the photo"),
      caption: z
        .string()
        .max(1024)
        .optional()
        .describe("Caption text below the photo (max 1024 chars)"),
      parse_mode: z
        .enum(["Markdown", "HTML", ""])
        .default("Markdown")
        .describe("Formatting mode for caption"),
      disable_notification: z.boolean().default(false),
    }),
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: true,
    },
  },
  async ({ chat_id, photo, caption, parse_mode, disable_notification }) => {
    try {
      const body: Record<string, unknown> = {
        chat_id,
        photo,
        disable_notification,
      };
      if (caption) body.caption = caption;
      if (parse_mode && caption) body.parse_mode = parse_mode;

      const result = await telegramCall<{ message_id: number }>(
        "sendPhoto",
        body
      );

      const output = { success: true, message_id: result.message_id };
      return {
        content: [{ type: "text", text: JSON.stringify(output, null, 2) }],
        structuredContent: output,
      };
    } catch (error) {
      return { content: [{ type: "text", text: apiError(error) }] };
    }
  }
);

// Tool: get_chat
server.registerTool(
  "telegram_get_chat",
  {
    title: "Get Telegram Chat Info",
    description: `Retrieve info about a Telegram chat or channel to verify bot access.

Use this to confirm the bot is correctly added to a chat before sending messages.

Args:
  - chat_id (string): Chat ID or @username

Returns:
  JSON with chat title, type, and member count.`,
    inputSchema: z.object({
      chat_id: z.string().describe("Chat ID or @username to look up"),
    }),
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true,
    },
  },
  async ({ chat_id }) => {
    try {
      const result = await telegramCall<{
        id: number;
        title?: string;
        username?: string;
        type: string;
        member_count?: number;
      }>("getChat", { chat_id });

      const output = {
        id: result.id,
        title: result.title,
        username: result.username,
        type: result.type,
        member_count: result.member_count,
      };
      return {
        content: [{ type: "text", text: JSON.stringify(output, null, 2) }],
        structuredContent: output,
      };
    } catch (error) {
      return { content: [{ type: "text", text: apiError(error) }] };
    }
  }
);

// ─── HTTP Server ────────────────────────────────────────────────────────────

async function main() {
  if (!BOT_TOKEN) {
    console.error("ERROR: TELEGRAM_BOT_TOKEN environment variable is required");
    process.exit(1);
  }

  const app = express();
  app.use(express.json());

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", server: "telegram-mcp-server" });
  });

  app.post("/mcp", async (req, res) => {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    res.on("close", () => transport.close());
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });

  app.listen(PORT, () => {
    console.error(`Telegram MCP server running on http://localhost:${PORT}/mcp`);
  });
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
