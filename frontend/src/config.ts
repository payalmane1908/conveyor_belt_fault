/**
 * System and Environment Configuration
 * 
 * Strict rule: No credentials or secrets in frontend code.
 * Adheres to SIH Hardware Prototype Capability Framework.
 */

export interface AppConfig {
  useMock: boolean;
  apiBaseUrl: string;
  wsBaseUrl: string;
  pollIntervalMs: number;
  plantName: string;
  conveyorId: string;
}

const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
const wsBase = apiBase.replace(/^http/, 'ws');

export const config: AppConfig = {
  useMock: import.meta.env.VITE_USE_MOCK === 'true',
  apiBaseUrl: apiBase,
  wsBaseUrl: wsBase,
  pollIntervalMs: Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 2000,
  plantName: 'IRON ORE BENEFICIATION PLANT',
  conveyorId: 'CV-MINE-01',
};
