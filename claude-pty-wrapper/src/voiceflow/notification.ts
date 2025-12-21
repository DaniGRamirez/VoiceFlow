/**
 * Notification Schema - Matches VoiceFlow's notification format.
 *
 * Based on core/event_server.py NotificationRequest schema.
 */

/**
 * Action button style.
 */
export type ActionStyle = 'primary' | 'secondary' | 'danger' | 'vscode';

/**
 * An action that can be taken on a notification.
 */
export interface NotificationAction {
  id: string;
  label: string;
  hotkey: string;
  style: ActionStyle;
}

/**
 * Notification type.
 */
export type NotificationType = 'confirmation' | 'choice' | 'info' | 'input';

/**
 * A notification request to VoiceFlow.
 */
export interface NotificationRequest {
  correlation_id: string;
  title: string;
  body: string;
  type: NotificationType;
  actions: NotificationAction[];
  source: string;
  timeout_seconds: number;
}

/**
 * Response from creating a notification.
 */
export interface NotificationResponse {
  success: boolean;
  correlation_id: string;
  message: string;
}

/**
 * An intent request to execute an action.
 */
export interface IntentRequest {
  correlation_id: string;
  intent: string;
  hotkey?: string;
  source: string;
}

/**
 * Response from executing an intent.
 */
export interface IntentResponse {
  success: boolean;
  correlation_id: string;
  intent: string;
  status: string;
}

/**
 * Server status response.
 */
export interface StatusResponse {
  status: string;
  notifications_count: number;
  pending_count: number;
  uptime_seconds: number;
}

/**
 * Create a notification for a tool that needs confirmation.
 *
 * @param toolId - The tool use ID (used as correlation_id)
 * @param toolName - Name of the tool (Write, Edit, Bash, etc.)
 * @param description - Human-readable description of the operation
 * @returns NotificationRequest ready to send to VoiceFlow
 */
export function createToolNotification(
  toolId: string,
  toolName: string,
  description: string
): NotificationRequest {
  return {
    correlation_id: toolId,
    title: `Claude Code - ${toolName}`,
    body: description,
    type: 'confirmation',
    actions: [
      {
        id: 'accept',
        label: 'Aceptar',
        hotkey: '1',
        style: 'primary'
      },
      {
        id: 'cancel',
        label: 'Cancelar',
        hotkey: 'escape',
        style: 'danger'
      }
    ],
    source: 'claude_pty_wrapper',
    timeout_seconds: 120
  };
}

/**
 * Create a notification with custom actions.
 *
 * @param correlationId - Unique ID for this notification
 * @param title - Notification title
 * @param body - Notification body text
 * @param actions - Array of actions
 * @param type - Notification type
 * @returns NotificationRequest ready to send to VoiceFlow
 */
export function createNotification(
  correlationId: string,
  title: string,
  body: string,
  actions: NotificationAction[],
  type: NotificationType = 'confirmation'
): NotificationRequest {
  return {
    correlation_id: correlationId,
    title,
    body,
    type,
    actions,
    source: 'claude_pty_wrapper',
    timeout_seconds: 120
  };
}
