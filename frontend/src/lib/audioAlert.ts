/**
 * Audio Alert Manager (Muted / Silent Mode)
 * Audio alerts have been disabled per operator preference.
 * Maintains API interface for UI components without emitting sound.
 */

class AudioAlertManager {
  private isMuted: boolean = true;

  constructor() {
    this.isMuted = true;
  }

  public toggleMute(): boolean {
    this.isMuted = !this.isMuted;
    return this.isMuted;
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  public playCriticalAlarm() {
    // Sound disabled per operator request
    return;
  }
}

export const audioAlert = new AudioAlertManager();
