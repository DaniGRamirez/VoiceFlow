/**
 * Auto-Approve - Determines which tools need user confirmation.
 *
 * Matches the existing VoiceFlow BASH_AUTO_APPROVED whitelist.
 */

/**
 * Bash commands that are auto-approved (no confirmation needed).
 * Matches the list in VoiceFlow's core/transcript_watcher.py
 */
const BASH_AUTO_APPROVED = [
  // Git commands
  'git add',
  'git commit',
  'git push',
  'git status',
  'git diff',
  'git log',
  'git checkout',
  'git branch',
  'git fetch',
  'git pull',
  'git stash',
  'git show',
  'git remote',
  'git config',

  // Python commands
  'python -c',
  'python -m py_compile',
  'python ',
  'python3 ',
  'timeout 5 python',
  'timeout 3 python',

  // Package managers
  'pip install',
  'pip list',
  'pip show',
  'pip freeze',
  'npm install',
  'npm run',
  'npm test',
  'npm build',
  'npm list',
  'yarn add',
  'yarn install',
  'yarn run',

  // Directory/file listing (read-only)
  'dir',
  'dir /s /b',
  'ls',
  'ls -',
  'pwd',
  'cd',
  'cat',
  'head',
  'tail',
  'wc',
  'echo',
  'type',
  'find',
  'grep',
  'rg',
  'tree',
  'stat',
  'file',

  // Build tools
  'make',
  'cargo build',
  'cargo run',
  'cargo test',
  'go build',
  'go run',
  'go test'
];

/**
 * Tools that require confirmation by default.
 */
const TOOLS_NEED_CONFIRM = new Set([
  'Write',
  'Edit',
  'NotebookEdit',
  'Bash'
]);

/**
 * Check if a Bash command is in the auto-approved whitelist.
 *
 * @param command - The Bash command to check
 * @returns true if auto-approved, false if confirmation needed
 */
export function isBashAutoApproved(command: string): boolean {
  const cmdLower = command.trim().toLowerCase();

  return BASH_AUTO_APPROVED.some(prefix =>
    cmdLower.startsWith(prefix.toLowerCase())
  );
}

/**
 * Check if a tool use needs user confirmation.
 *
 * @param toolName - Name of the tool
 * @param toolInput - Tool input parameters
 * @returns true if confirmation is needed, false if auto-approved
 */
export function needsConfirmation(toolName: string, toolInput: Record<string, unknown>): boolean {
  // If not in the list of tools that need confirmation, auto-approve
  if (!TOOLS_NEED_CONFIRM.has(toolName)) {
    return false;
  }

  // For Bash, check against the whitelist
  if (toolName === 'Bash') {
    const command = (toolInput.command as string) || '';
    return !isBashAutoApproved(command);
  }

  // All other tools in TOOLS_NEED_CONFIRM require confirmation
  return true;
}

/**
 * Add a command pattern to the auto-approve whitelist.
 * Useful for runtime configuration.
 *
 * @param pattern - Command prefix pattern to auto-approve
 */
export function addAutoApprovePattern(pattern: string): void {
  if (!BASH_AUTO_APPROVED.includes(pattern)) {
    BASH_AUTO_APPROVED.push(pattern);
  }
}

/**
 * Get the current auto-approve whitelist.
 *
 * @returns Copy of the auto-approve patterns
 */
export function getAutoApprovePatterns(): string[] {
  return [...BASH_AUTO_APPROVED];
}
