/**
 * Session Manager - Manages wrapper session lifecycle.
 *
 * Each wrapper instance = one session with unique ID.
 */

import { v4 as uuidv4 } from 'uuid';
import { EventEmitter } from 'events';

/**
 * Information about a pending tool.
 */
export interface PendingTool {
  name: string;
  timestamp: Date;
  notificationSent: boolean;
}

/**
 * A wrapper session.
 */
export interface Session {
  id: string;
  startTime: Date;
  endTime?: Date;
  projectPath: string;
  cwd: string;
  pendingTools: Map<string, PendingTool>;
  completedTools: number;
  active: boolean;
}

/**
 * Session events.
 */
export interface SessionEvents {
  'session_start': (session: Session) => void;
  'session_end': (session: Session) => void;
  'tool_pending': (sessionId: string, toolId: string, toolName: string) => void;
  'tool_resolved': (sessionId: string, toolId: string) => void;
}

/**
 * Manages wrapper sessions.
 */
export class SessionManager extends EventEmitter {
  private sessions: Map<string, Session> = new Map();

  /**
   * Create a new session.
   *
   * @param projectPath - Path to Claude project directory
   * @param cwd - Current working directory
   * @returns The new session
   */
  createSession(projectPath: string, cwd: string): Session {
    const session: Session = {
      id: uuidv4(),
      startTime: new Date(),
      projectPath,
      cwd,
      pendingTools: new Map(),
      completedTools: 0,
      active: true
    };

    this.sessions.set(session.id, session);
    console.log(`[Session] Created: ${session.id.substring(0, 8)}...`);
    this.emit('session_start', session);

    return session;
  }

  /**
   * Get a session by ID.
   *
   * @param sessionId - Session ID
   * @returns Session or undefined
   */
  getSession(sessionId: string): Session | undefined {
    return this.sessions.get(sessionId);
  }

  /**
   * Track a new tool use that needs confirmation.
   *
   * @param sessionId - Session ID
   * @param toolId - Tool use ID
   * @param toolName - Name of the tool
   */
  trackToolUse(sessionId: string, toolId: string, toolName: string): void {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return;
    }

    session.pendingTools.set(toolId, {
      name: toolName,
      timestamp: new Date(),
      notificationSent: false
    });

    this.emit('tool_pending', sessionId, toolId, toolName);
  }

  /**
   * Mark that a notification was sent for a tool.
   *
   * @param sessionId - Session ID
   * @param toolId - Tool use ID
   */
  markNotificationSent(sessionId: string, toolId: string): void {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return;
    }

    const tool = session.pendingTools.get(toolId);
    if (tool) {
      tool.notificationSent = true;
    }
  }

  /**
   * Resolve a pending tool (tool completed).
   *
   * @param sessionId - Session ID
   * @param toolId - Tool use ID
   */
  resolveToolUse(sessionId: string, toolId: string): void {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return;
    }

    if (session.pendingTools.has(toolId)) {
      session.pendingTools.delete(toolId);
      session.completedTools++;
      this.emit('tool_resolved', sessionId, toolId);
    }
  }

  /**
   * End a session.
   *
   * @param sessionId - Session ID
   */
  endSession(sessionId: string): void {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return;
    }

    session.active = false;
    session.endTime = new Date();

    console.log(`[Session] Ended: ${sessionId.substring(0, 8)}... (${session.completedTools} tools completed)`);
    this.emit('session_end', session);
  }

  /**
   * Get all active sessions.
   *
   * @returns Array of active sessions
   */
  getActiveSessions(): Session[] {
    return Array.from(this.sessions.values()).filter(s => s.active);
  }

  /**
   * Get total count of pending tools across all sessions.
   *
   * @returns Number of pending tools
   */
  getPendingCount(): number {
    let count = 0;
    for (const session of this.sessions.values()) {
      if (session.active) {
        count += session.pendingTools.size;
      }
    }
    return count;
  }

  /**
   * Find session by tool ID.
   *
   * @param toolId - Tool use ID
   * @returns Session ID or undefined
   */
  findSessionByToolId(toolId: string): string | undefined {
    for (const [sessionId, session] of this.sessions) {
      if (session.pendingTools.has(toolId)) {
        return sessionId;
      }
    }
    return undefined;
  }

  /**
   * Get session summary for logging.
   *
   * @param sessionId - Session ID
   * @returns Summary string
   */
  getSessionSummary(sessionId: string): string {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return 'Session not found';
    }

    const duration = session.endTime
      ? (session.endTime.getTime() - session.startTime.getTime()) / 1000
      : (Date.now() - session.startTime.getTime()) / 1000;

    return `Session ${sessionId.substring(0, 8)}: ${session.completedTools} tools, ${session.pendingTools.size} pending, ${duration.toFixed(1)}s`;
  }

  /**
   * Clean up old ended sessions.
   *
   * @param maxAgeMs - Maximum age in milliseconds (default 5 minutes)
   */
  cleanup(maxAgeMs: number = 300000): void {
    const now = Date.now();

    for (const [sessionId, session] of this.sessions) {
      if (!session.active && session.endTime) {
        if (now - session.endTime.getTime() > maxAgeMs) {
          this.sessions.delete(sessionId);
        }
      }
    }
  }
}
