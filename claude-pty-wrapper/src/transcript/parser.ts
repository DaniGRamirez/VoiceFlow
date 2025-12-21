/**
 * Transcript Parser - Parses Claude Code transcript .jsonl files.
 *
 * Extracts tool_use and tool_result blocks from the JSON lines.
 */

/**
 * A tool_use block from an assistant message.
 */
export interface ToolUseBlock {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

/**
 * A tool_result block from a user message.
 */
export interface ToolResultBlock {
  tool_use_id: string;
  content: unknown;
  is_error?: boolean;
}

/**
 * Content block in a message.
 */
interface ContentBlock {
  type: string;
  id?: string;
  name?: string;
  input?: Record<string, unknown>;
  tool_use_id?: string;
  content?: unknown;
  is_error?: boolean;
  text?: string;
}

/**
 * A line from the transcript .jsonl file.
 */
export interface TranscriptLine {
  type: 'assistant' | 'user' | 'system';
  message?: {
    content: ContentBlock[];
  };
  timestamp?: string;
}

/**
 * Parse a single line from the transcript file.
 *
 * @param line - A single line from the .jsonl file
 * @returns Parsed transcript line or null if invalid
 */
export function parseTranscriptLine(line: string): TranscriptLine | null {
  const trimmed = line.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed) as TranscriptLine;
  } catch {
    // Invalid JSON, skip
    return null;
  }
}

/**
 * Extract tool_use blocks from a transcript line.
 *
 * Tool uses appear in assistant messages when Claude wants to execute a tool.
 *
 * @param data - Parsed transcript line
 * @returns Array of tool_use blocks
 */
export function extractToolUse(data: TranscriptLine): ToolUseBlock[] {
  if (data.type !== 'assistant') {
    return [];
  }

  const content = data.message?.content;
  if (!Array.isArray(content)) {
    return [];
  }

  return content
    .filter((block): block is ContentBlock & { type: 'tool_use'; id: string; name: string } =>
      block.type === 'tool_use' && typeof block.id === 'string' && typeof block.name === 'string'
    )
    .map(block => ({
      id: block.id,
      name: block.name,
      input: block.input || {}
    }));
}

/**
 * Extract tool_result blocks from a transcript line.
 *
 * Tool results appear in user messages after a tool has been executed.
 *
 * @param data - Parsed transcript line
 * @returns Array of tool_result blocks
 */
export function extractToolResult(data: TranscriptLine): ToolResultBlock[] {
  if (data.type !== 'user') {
    return [];
  }

  const content = data.message?.content;
  if (!Array.isArray(content)) {
    return [];
  }

  return content
    .filter((block): block is ContentBlock & { type: 'tool_result'; tool_use_id: string } =>
      block.type === 'tool_result' && typeof block.tool_use_id === 'string'
    )
    .map(block => ({
      tool_use_id: block.tool_use_id,
      content: block.content,
      is_error: block.is_error
    }));
}

/**
 * Get a human-readable description of a tool use.
 *
 * @param toolName - Name of the tool
 * @param toolInput - Tool input parameters
 * @returns Human-readable description
 */
export function getToolDescription(toolName: string, toolInput: Record<string, unknown>): string {
  switch (toolName) {
    case 'Write': {
      const filePath = (toolInput.file_path as string) || 'unknown';
      return `Crear: ${getFileName(filePath)}`;
    }
    case 'Edit': {
      const filePath = (toolInput.file_path as string) || 'unknown';
      return `Editar: ${getFileName(filePath)}`;
    }
    case 'Bash': {
      const command = ((toolInput.command as string) || '').substring(0, 60);
      return `$ ${command}${(toolInput.command as string)?.length > 60 ? '...' : ''}`;
    }
    case 'NotebookEdit': {
      const notebookPath = (toolInput.notebook_path as string) || 'unknown';
      return `Notebook: ${getFileName(notebookPath)}`;
    }
    default:
      return toolName;
  }
}

/**
 * Extract filename from a path.
 */
function getFileName(filePath: string): string {
  return filePath.split(/[/\\]/).pop() || filePath;
}
