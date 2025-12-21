/**
 * VoiceFlow Client - HTTP client for VoiceFlow Event Server.
 *
 * Sends notifications and dismisses them when tools complete.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  NotificationRequest,
  NotificationResponse,
  IntentRequest,
  IntentResponse,
  StatusResponse
} from './notification';

/**
 * Options for the VoiceFlow client.
 */
export interface VoiceFlowClientOptions {
  baseUrl?: string;
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

/**
 * HTTP client for communicating with VoiceFlow Event Server.
 */
export class VoiceFlowClient {
  private client: AxiosInstance;
  private baseUrl: string;
  private retries: number;
  private retryDelay: number;

  constructor(options: VoiceFlowClientOptions = {}) {
    this.baseUrl = options.baseUrl || 'http://localhost:8765';
    this.retries = options.retries ?? 2;
    this.retryDelay = options.retryDelay ?? 500;

    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: options.timeout ?? 2000,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * Send a notification to VoiceFlow.
   *
   * @param notification - The notification to send
   * @returns true if successful, false otherwise
   */
  async sendNotification(notification: NotificationRequest): Promise<boolean> {
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        const response = await this.client.post<NotificationResponse>(
          '/api/notification',
          notification
        );

        if (response.status === 200 && response.data.success) {
          console.log(`[VoiceFlow] Notification sent: ${notification.title}`);
          return true;
        }
      } catch (error) {
        const isLastAttempt = attempt === this.retries;
        const axiosError = error as AxiosError;

        if (axiosError.code === 'ECONNREFUSED') {
          if (isLastAttempt) {
            console.log(`[VoiceFlow] Server not available at ${this.baseUrl}`);
          }
        } else if (isLastAttempt) {
          console.log(`[VoiceFlow] Error sending notification: ${axiosError.message}`);
        }

        if (!isLastAttempt) {
          await this.delay(this.retryDelay);
        }
      }
    }

    return false;
  }

  /**
   * Dismiss a notification (when a tool completes).
   *
   * @param correlationId - The correlation ID of the notification to dismiss
   * @returns true if successful, false otherwise
   */
  async dismissNotification(correlationId: string): Promise<boolean> {
    try {
      const response = await this.client.delete(`/api/notification/${correlationId}`);

      if (response.status === 200) {
        console.log(`[VoiceFlow] Dismissed: ${correlationId.substring(0, 12)}...`);
        return true;
      }
    } catch (error) {
      const axiosError = error as AxiosError;
      // Silently ignore 404 (notification already dismissed)
      if (axiosError.response?.status !== 404) {
        // Only log unexpected errors
        if (axiosError.code !== 'ECONNREFUSED') {
          console.log(`[VoiceFlow] Error dismissing: ${axiosError.message}`);
        }
      }
    }

    return false;
  }

  /**
   * Send an intent to execute an action.
   *
   * @param intent - The intent to execute
   * @returns true if successful, false otherwise
   */
  async sendIntent(intent: IntentRequest): Promise<boolean> {
    try {
      const response = await this.client.post<IntentResponse>(
        '/api/intent',
        intent
      );

      if (response.status === 200 && response.data.success) {
        console.log(`[VoiceFlow] Intent executed: ${intent.intent}`);
        return true;
      }
    } catch (error) {
      const axiosError = error as AxiosError;
      console.log(`[VoiceFlow] Error sending intent: ${axiosError.message}`);
    }

    return false;
  }

  /**
   * Get the server status.
   *
   * @returns Status response or null if unavailable
   */
  async getStatus(): Promise<StatusResponse | null> {
    try {
      const response = await this.client.get<StatusResponse>('/api/status');
      return response.data;
    } catch {
      return null;
    }
  }

  /**
   * Check if the server is available.
   *
   * @returns true if server is responding, false otherwise
   */
  async isAvailable(): Promise<boolean> {
    const status = await this.getStatus();
    return status !== null && status.status === 'running';
  }

  /**
   * Get all pending notifications.
   *
   * @returns Array of notifications or empty array
   */
  async getNotifications(): Promise<any[]> {
    try {
      const response = await this.client.get('/api/notifications');
      return response.data.notifications || [];
    } catch {
      return [];
    }
  }

  /**
   * Helper to delay execution.
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get the base URL.
   */
  get url(): string {
    return this.baseUrl;
  }
}
