/**
 * Correlation Tracker - Maps tool IDs to sessions and tracks resolution.
 *
 * Used to ensure proper routing of intents and dismissals.
 */

/**
 * A correlation entry linking a tool to its session.
 */
export interface CorrelationEntry {
  toolId: string;
  toolName: string;
  sessionId: string;
  notificationSent: boolean;
  timestamp: Date;
  resolved: boolean;
  resolvedAt?: Date;
}

/**
 * Tracks correlation between tool IDs and sessions.
 */
export class CorrelationTracker {
  private entries: Map<string, CorrelationEntry> = new Map();

  /**
   * Track a new tool use.
   *
   * @param toolId - Tool use ID
   * @param toolName - Name of the tool
   * @param sessionId - Session ID
   */
  track(toolId: string, toolName: string, sessionId: string): void {
    this.entries.set(toolId, {
      toolId,
      toolName,
      sessionId,
      notificationSent: false,
      timestamp: new Date(),
      resolved: false
    });
  }

  /**
   * Mark that a notification was sent for this tool.
   *
   * @param toolId - Tool use ID
   */
  markNotificationSent(toolId: string): void {
    const entry = this.entries.get(toolId);
    if (entry) {
      entry.notificationSent = true;
    }
  }

  /**
   * Mark a tool as resolved.
   *
   * @param toolId - Tool use ID
   */
  markResolved(toolId: string): void {
    const entry = this.entries.get(toolId);
    if (entry) {
      entry.resolved = true;
      entry.resolvedAt = new Date();
    }
  }

  /**
   * Get a correlation entry.
   *
   * @param toolId - Tool use ID
   * @returns Correlation entry or undefined
   */
  get(toolId: string): CorrelationEntry | undefined {
    return this.entries.get(toolId);
  }

  /**
   * Check if a tool is tracked.
   *
   * @param toolId - Tool use ID
   * @returns true if tracked
   */
  has(toolId: string): boolean {
    return this.entries.has(toolId);
  }

  /**
   * Get all pending (unresolved) entries.
   *
   * @returns Array of pending entries
   */
  getPending(): CorrelationEntry[] {
    return Array.from(this.entries.values())
      .filter(e => e.notificationSent && !e.resolved);
  }

  /**
   * Get entries for a specific session.
   *
   * @param sessionId - Session ID
   * @returns Array of entries for the session
   */
  getBySession(sessionId: string): CorrelationEntry[] {
    return Array.from(this.entries.values())
      .filter(e => e.sessionId === sessionId);
  }

  /**
   * Get pending entries for a specific session.
   *
   * @param sessionId - Session ID
   * @returns Array of pending entries for the session
   */
  getPendingBySession(sessionId: string): CorrelationEntry[] {
    return Array.from(this.entries.values())
      .filter(e => e.sessionId === sessionId && e.notificationSent && !e.resolved);
  }

  /**
   * Clean up old resolved entries.
   *
   * @param maxAgeMs - Maximum age in milliseconds (default 5 minutes)
   */
  cleanup(maxAgeMs: number = 300000): void {
    const now = Date.now();

    for (const [toolId, entry] of this.entries) {
      if (entry.resolved && entry.resolvedAt) {
        if (now - entry.resolvedAt.getTime() > maxAgeMs) {
          this.entries.delete(toolId);
        }
      }
    }
  }

  /**
   * Get statistics about tracked tools.
   *
   * @returns Object with counts
   */
  getStats(): { total: number; pending: number; resolved: number } {
    let pending = 0;
    let resolved = 0;

    for (const entry of this.entries.values()) {
      if (entry.resolved) {
        resolved++;
      } else if (entry.notificationSent) {
        pending++;
      }
    }

    return {
      total: this.entries.size,
      pending,
      resolved
    };
  }

  /**
   * Clear all entries.
   */
  clear(): void {
    this.entries.clear();
  }
}
