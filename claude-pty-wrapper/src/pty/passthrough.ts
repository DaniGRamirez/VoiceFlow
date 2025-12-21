/**
 * Passthrough - Handles signal handlers and cleanup.
 *
 * With child_process using stdio: 'inherit' for stdin,
 * input is automatically forwarded to the child process.
 */

import { ClaudePtySpawner } from './spawner';

/**
 * Setup stdin passthrough to the child process.
 *
 * Note: With stdio: 'inherit' for stdin in spawner.ts,
 * this is mostly a no-op since stdin is already connected.
 */
export function setupInputPassthrough(_spawner: ClaudePtySpawner): void {
  // stdin is inherited directly by the child process
  // No additional setup needed
}

/**
 * Cleanup stdin when process exits.
 */
export function cleanupPassthrough(): void {
  // Nothing to clean up when using inherited stdio
}

/**
 * Setup signal handlers for graceful shutdown.
 */
export function setupSignalHandlers(spawner: ClaudePtySpawner, cleanup: () => void): void {
  const handleSignal = (signal: string) => {
    console.log(`\n[Wrapper] Received ${signal}, cleaning up...`);
    spawner.kill();
    cleanup();
    process.exit(0);
  };

  // Handle common termination signals
  process.on('SIGINT', () => handleSignal('SIGINT'));
  process.on('SIGTERM', () => handleSignal('SIGTERM'));

  // Windows-specific
  if (process.platform === 'win32') {
    process.on('SIGBREAK', () => handleSignal('SIGBREAK'));
  }
}
