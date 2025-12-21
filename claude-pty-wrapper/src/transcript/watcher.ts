/**
 * Transcript Watcher - Monitors Claude Code transcript files for tool uses.
 *
 * Uses chokidar to watch .jsonl files and emits events when tools need confirmation.
 */

import * as chokidar from 'chokidar';
import * as fs from 'fs';
import * as path from 'path';
import { EventEmitter } from 'events';
import {
  parseTranscriptLine,
  extractToolUse,
  extractToolResult,
  getToolDescription,
  ToolUseBlock,
  ToolResultBlock
} from './parser';
import { needsConfirmation } from './auto-approve';

/**
 * Event emitted when a tool needs confirmation.
 */
export interface ToolUseEvent {
  id: string;
  name: string;
  input: Record<string, unknown>;
  description: string;
}

/**
 * Event emitted when a tool completes.
 */
export interface ToolCompleteEvent {
  tool_use_id: string;
  is_error?: boolean;
}

/**
 * Watcher events.
 */
export interface WatcherEvents {
  'tool_use': (event: ToolUseEvent) => void;
  'tool_complete': (event: ToolCompleteEvent) => void;
  'error': (error: Error) => void;
  'watching': (filePath: string) => void;
}

/**
 * Watches Claude Code transcript files for tool uses.
 */
export class TranscriptWatcher extends EventEmitter {
  private watcher: chokidar.FSWatcher | null = null;
  private filePositions: Map<string, number> = new Map();
  private seenToolIds: Set<string> = new Set();
  private seenResultIds: Set<string> = new Set();
  private projectPath: string;
  private running: boolean = false;

  constructor(projectPath: string) {
    super();
    this.projectPath = projectPath;
  }

  /**
   * Start watching transcript files.
   */
  start(): void {
    if (this.running) {
      return;
    }
    this.running = true;

    // Watch for .jsonl files in the project directory
    const pattern = path.join(this.projectPath, '*.jsonl');

    this.watcher = chokidar.watch(pattern, {
      persistent: true,
      ignoreInitial: false,
      awaitWriteFinish: {
        stabilityThreshold: 100,
        pollInterval: 50
      },
      // Use polling on Windows for better reliability
      usePolling: process.platform === 'win32',
      interval: 100
    });

    this.watcher.on('add', (filePath) => this.onFileAdded(filePath));
    this.watcher.on('change', (filePath) => this.onFileChanged(filePath));
    this.watcher.on('error', (error) => this.emit('error', error));

    console.log(`[Watcher] Monitoring: ${this.projectPath}`);
  }

  /**
   * Handle a new file being added to watch.
   */
  private onFileAdded(filePath: string): void {
    try {
      // Start reading from end of file (ignore history)
      const stats = fs.statSync(filePath);
      this.filePositions.set(filePath, stats.size);
      console.log(`[Watcher] Watching: ${path.basename(filePath)}`);
      this.emit('watching', filePath);
    } catch (error) {
      this.emit('error', error as Error);
    }
  }

  /**
   * Handle file content changes.
   */
  private onFileChanged(filePath: string): void {
    const position = this.filePositions.get(filePath) || 0;

    let fd: number | undefined;
    try {
      fd = fs.openSync(filePath, 'r');
      const stats = fs.fstatSync(fd);
      const newSize = stats.size;

      // File was truncated or unchanged
      if (newSize <= position) {
        if (newSize < position) {
          // File was truncated, reset position
          this.filePositions.set(filePath, newSize);
        }
        return;
      }

      // Read new content
      const buffer = Buffer.alloc(newSize - position);
      fs.readSync(fd, buffer, 0, buffer.length, position);
      this.filePositions.set(filePath, newSize);

      const content = buffer.toString('utf-8');
      const lines = content.split('\n').filter(l => l.trim());

      for (const line of lines) {
        this.processLine(line);
      }
    } catch (error) {
      this.emit('error', error as Error);
    } finally {
      if (fd !== undefined) {
        try {
          fs.closeSync(fd);
        } catch {
          // Ignore close errors
        }
      }
    }
  }

  /**
   * Process a single line from the transcript.
   */
  private processLine(line: string): void {
    const data = parseTranscriptLine(line);
    if (!data) {
      return;
    }

    // Detect tool_use (assistant executing a tool)
    const toolUses = extractToolUse(data);
    for (const tool of toolUses) {
      if (!this.seenToolIds.has(tool.id)) {
        this.seenToolIds.add(tool.id);

        if (needsConfirmation(tool.name, tool.input)) {
          const description = getToolDescription(tool.name, tool.input);
          const event: ToolUseEvent = {
            id: tool.id,
            name: tool.name,
            input: tool.input,
            description
          };
          console.log(`[Watcher] Tool: ${tool.name} (ID: ${tool.id.substring(0, 12)}...)`);
          this.emit('tool_use', event);
        }
      }
    }

    // Detect tool_result (tool completed)
    const results = extractToolResult(data);
    for (const result of results) {
      if (!this.seenResultIds.has(result.tool_use_id)) {
        this.seenResultIds.add(result.tool_use_id);
        const event: ToolCompleteEvent = {
          tool_use_id: result.tool_use_id,
          is_error: result.is_error
        };
        console.log(`[Watcher] Completed: ${result.tool_use_id.substring(0, 12)}...`);
        this.emit('tool_complete', event);
      }
    }
  }

  /**
   * Stop watching transcript files.
   */
  stop(): void {
    this.running = false;
    if (this.watcher) {
      this.watcher.close();
      this.watcher = null;
    }
    console.log('[Watcher] Stopped');
  }

  /**
   * Check if the watcher is running.
   */
  get isRunning(): boolean {
    return this.running;
  }

  /**
   * Get the set of seen tool IDs.
   */
  get seenTools(): Set<string> {
    return new Set(this.seenToolIds);
  }

  /**
   * Clear the seen tool IDs (for testing).
   */
  clearSeen(): void {
    this.seenToolIds.clear();
    this.seenResultIds.clear();
  }
}

/**
 * Find the Claude project path for the current working directory.
 *
 * Claude stores projects in ~/.claude/projects/<sanitized-path>
 */
export function findProjectPath(cwd: string): string {
  const home = process.env.HOME || process.env.USERPROFILE || '';
  const claudeProjectsDir = path.join(home, '.claude', 'projects');

  // Sanitize the cwd to match Claude's project naming
  // Claude uses a sanitized version of the full path
  const sanitized = cwd
    .replace(/[<>:"|?*]/g, '')  // Remove invalid chars
    .replace(/\\/g, '-')         // Replace backslashes
    .replace(/\//g, '-')         // Replace forward slashes
    .replace(/^-+/, '')          // Remove leading dashes
    .replace(/-+$/, '')          // Remove trailing dashes
    .replace(/-+/g, '-');        // Collapse multiple dashes

  // Try to find a matching project
  const projectPath = path.join(claudeProjectsDir, sanitized);

  // If the exact path doesn't exist, try to find a partial match
  if (!fs.existsSync(projectPath)) {
    try {
      const projects = fs.readdirSync(claudeProjectsDir);
      // Look for a project that contains the last part of the path
      const lastPart = path.basename(cwd).toLowerCase();
      const match = projects.find(p => p.toLowerCase().includes(lastPart));
      if (match) {
        return path.join(claudeProjectsDir, match);
      }
    } catch {
      // Directory doesn't exist yet
    }
  }

  return projectPath;
}
