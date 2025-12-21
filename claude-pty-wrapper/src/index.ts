#!/usr/bin/env node
/**
 * Claude PTY Wrapper - Main entry point.
 *
 * Spawns Claude CLI as a PTY, monitors transcripts, and sends notifications to VoiceFlow.
 *
 * Usage:
 *   claude-wrapper [claude args...]
 *   claude-wrapper --help
 */

import { Command } from 'commander';
import * as path from 'path';
import * as fs from 'fs';

import { ClaudePtySpawner, setupInputPassthrough, cleanupPassthrough, setupSignalHandlers } from './pty';
import { TranscriptWatcher, findProjectPath, ToolUseEvent, ToolCompleteEvent } from './transcript';
import { VoiceFlowClient, createToolNotification } from './voiceflow';
import { SessionManager } from './session';
import { CorrelationTracker } from './session/correlation';

// Version from package.json
const packageJsonPath = path.join(__dirname, '..', 'package.json');
let version = '1.0.0';
try {
  const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
  version = pkg.version;
} catch {
  // Ignore
}

/**
 * Main wrapper function.
 */
async function main(): Promise<void> {
  const program = new Command();

  program
    .name('claude-wrapper')
    .description('PTY wrapper for Claude Code CLI with VoiceFlow notification integration')
    .version(version)
    .option('--voiceflow-url <url>', 'VoiceFlow server URL', 'http://localhost:8765')
    .option('--no-voiceflow', 'Disable VoiceFlow integration')
    .option('--claude-path <path>', 'Path to Claude CLI executable')
    .option('--project <path>', 'Claude project path (auto-detected if not specified)')
    .option('--debug', 'Enable debug logging')
    .allowUnknownOption(true)
    .allowExcessArguments(true);

  // Parse our own options, pass the rest to Claude
  const parsed = program.parse(process.argv);
  const opts = program.opts();

  // Get remaining args for Claude
  const claudeArgs = parsed.args;

  // Current working directory
  const cwd = process.cwd();

  // Debug mode
  const debug = opts.debug;
  if (debug) {
    console.log('[Wrapper] Debug mode enabled');
    console.log(`[Wrapper] CWD: ${cwd}`);
    console.log(`[Wrapper] Claude args: ${claudeArgs.join(' ')}`);
  }

  // Find Claude project path
  const projectPath = opts.project || findProjectPath(cwd);
  if (debug) {
    console.log(`[Wrapper] Project path: ${projectPath}`);
  }

  // Initialize components
  const sessionManager = new SessionManager();
  const correlationTracker = new CorrelationTracker();
  const voiceflowClient = opts.voiceflow
    ? new VoiceFlowClient({ baseUrl: opts.voiceflowUrl })
    : null;

  // Create session
  const session = sessionManager.createSession(projectPath, cwd);

  // Initialize transcript watcher
  const watcher = new TranscriptWatcher(projectPath);

  // Wire up watcher events
  watcher.on('tool_use', async (event: ToolUseEvent) => {
    // Track the tool
    sessionManager.trackToolUse(session.id, event.id, event.name);
    correlationTracker.track(event.id, event.name, session.id);

    // Send notification to VoiceFlow
    if (voiceflowClient) {
      const notification = createToolNotification(event.id, event.name, event.description);
      const success = await voiceflowClient.sendNotification(notification);

      if (success) {
        sessionManager.markNotificationSent(session.id, event.id);
        correlationTracker.markNotificationSent(event.id);
      }
    }
  });

  watcher.on('tool_complete', async (event: ToolCompleteEvent) => {
    // Resolve the tool
    sessionManager.resolveToolUse(session.id, event.tool_use_id);
    correlationTracker.markResolved(event.tool_use_id);

    // Dismiss notification in VoiceFlow
    if (voiceflowClient) {
      await voiceflowClient.dismissNotification(event.tool_use_id);
    }
  });

  watcher.on('error', (error: Error) => {
    console.error(`[Watcher] Error: ${error.message}`);
  });

  // Start the watcher
  watcher.start();

  // Initialize PTY spawner
  const pty = new ClaudePtySpawner(session.id);

  // Setup cleanup function
  const cleanup = () => {
    watcher.stop();
    sessionManager.endSession(session.id);
    cleanupPassthrough();
  };

  // Setup signal handlers
  setupSignalHandlers(pty, cleanup);

  // Handle PTY exit
  pty.on('exit', (exitCode: number) => {
    cleanup();

    if (debug) {
      console.log(`[Wrapper] Claude exited with code ${exitCode}`);
      console.log(`[Wrapper] ${sessionManager.getSessionSummary(session.id)}`);
    }

    process.exit(exitCode);
  });

  pty.on('error', (error: Error) => {
    console.error(`[Wrapper] PTY error: ${error.message}`);
    cleanup();
    process.exit(1);
  });

  // Spawn Claude
  pty.spawn({
    claudePath: opts.claudePath,
    args: claudeArgs,
    cwd
  });

  // Setup stdin passthrough
  setupInputPassthrough(pty);
}

// Run main
main().catch(error => {
  console.error(`[Wrapper] Fatal error: ${error.message}`);
  process.exit(1);
});
