/**
 * Process Spawner - Spawns Claude CLI as a child process.
 *
 * Uses child_process.spawn instead of node-pty to avoid native compilation.
 * Provides console passthrough so user sees normal Claude output.
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as os from 'os';

export interface SpawnOptions {
  claudePath?: string;      // Path to real claude CLI (auto-detected if not specified)
  args: string[];           // CLI arguments to forward
  cwd: string;              // Working directory
  env?: NodeJS.ProcessEnv;  // Additional environment variables
}

// Keep old name for compatibility
export type PtyOptions = SpawnOptions;

export interface SpawnerEvents {
  'output': (data: string) => void;
  'exit': (exitCode: number) => void;
  'error': (error: Error) => void;
}

export class ClaudePtySpawner extends EventEmitter {
  private childProcess: ChildProcess | null = null;
  private sessionId: string;
  private exited: boolean = false;

  constructor(sessionId: string) {
    super();
    this.sessionId = sessionId;
  }

  /**
   * Detect the path to the real Claude CLI.
   */
  private detectClaudePath(): string {
    if (process.platform === 'win32') {
      // Windows: Claude is typically installed here
      const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
      return path.join(localAppData, 'Programs', 'claude-code', 'claude.exe');
    } else {
      // macOS/Linux: assume claude is in PATH
      return 'claude';
    }
  }

  /**
   * Spawn Claude CLI as a child process.
   */
  spawn(options: SpawnOptions): void {
    const claudePath = options.claudePath || this.detectClaudePath();

    // Prepare environment
    const env = {
      ...process.env,
      ...options.env,
      CLAUDE_SESSION_ID: this.sessionId,
      // Ensure color output
      FORCE_COLOR: '1'
    };

    try {
      // Spawn the process with stdio inheritance for interactive mode
      this.childProcess = spawn(claudePath, options.args, {
        cwd: options.cwd,
        env: env as NodeJS.ProcessEnv,
        stdio: ['inherit', 'pipe', 'pipe'],
        shell: process.platform === 'win32'
      });

      // Forward stdout to console and emit event
      if (this.childProcess.stdout) {
        this.childProcess.stdout.on('data', (data: Buffer) => {
          const text = data.toString();
          process.stdout.write(text);
          this.emit('output', text);
        });
      }

      // Forward stderr to console
      if (this.childProcess.stderr) {
        this.childProcess.stderr.on('data', (data: Buffer) => {
          const text = data.toString();
          process.stderr.write(text);
          this.emit('output', text);
        });
      }

      // Handle exit
      this.childProcess.on('exit', (code: number | null) => {
        this.exited = true;
        this.emit('exit', code ?? 0);
      });

      // Handle errors
      this.childProcess.on('error', (error: Error) => {
        this.emit('error', error);
      });

    } catch (error) {
      this.emit('error', error as Error);
    }
  }

  /**
   * Write data to stdin (forward user input).
   * Note: With stdio: 'inherit' for stdin, this won't be used.
   */
  write(data: string): void {
    if (this.childProcess?.stdin && !this.exited) {
      this.childProcess.stdin.write(data);
    }
  }

  /**
   * Resize is not supported without PTY.
   * Kept for API compatibility.
   */
  resize(_cols: number, _rows: number): void {
    // No-op: resize not supported with child_process
  }

  /**
   * Kill the child process.
   */
  kill(): void {
    if (this.childProcess && !this.exited) {
      this.childProcess.kill();
    }
  }

  /**
   * Check if the process has exited.
   */
  get hasExited(): boolean {
    return this.exited;
  }

  /**
   * Get the session ID.
   */
  get id(): string {
    return this.sessionId;
  }
}
