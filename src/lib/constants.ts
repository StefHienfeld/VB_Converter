/**
 * Application constants for the Hienfeld VB Converter frontend.
 *
 * Centralizes configuration values that were previously hardcoded.
 * Makes tuning and testing easier.
 */

// ---------------------------------------------------------------------------
// API Configuration
// ---------------------------------------------------------------------------

export const API_CONFIG = {
  /** Base URL for API requests (from environment or default) */
  BASE_URL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",

  /** Default timeout for API calls in milliseconds */
  TIMEOUT_MS: 30000,

  /** Enable debug logging in development */
  DEBUG: import.meta.env.DEV,
} as const;

// ---------------------------------------------------------------------------
// Polling Configuration
// ---------------------------------------------------------------------------

export const POLLING_CONFIG = {
  /** Interval between status polls in milliseconds */
  INTERVAL_MS: 1500,

  /** Maximum retries on network errors before giving up */
  MAX_RETRIES: 3,

  /** Base delay multiplier for exponential backoff */
  BACKOFF_MULTIPLIER: 2,
} as const;

// ---------------------------------------------------------------------------
// UI Configuration
// ---------------------------------------------------------------------------

export const UI_CONFIG = {
  /** Maximum text length to display before truncating */
  MAX_DISPLAY_TEXT_LENGTH: 500,

  /** Default filename for downloaded reports */
  DEFAULT_REPORT_FILENAME: "Hienfeld_Analyse.xlsx",

  /** Toast notification durations in milliseconds */
  TOAST_DURATION_MS: 5000,
} as const;

// ---------------------------------------------------------------------------
// Analysis Settings Defaults
// ---------------------------------------------------------------------------

export const ANALYSIS_DEFAULTS = {
  /** Default cluster accuracy (similarity threshold) */
  CLUSTER_ACCURACY: 90,

  /** Default minimum frequency for standardization */
  MIN_FREQUENCY: 20,

  /** Default window size for leader algorithm */
  WINDOW_SIZE: 100,

  /** Default analysis mode */
  ANALYSIS_MODE: "balanced" as const,

  /** Whether AI is enabled by default */
  AI_ENABLED: false,
} as const;

// ---------------------------------------------------------------------------
// Progress Step Configuration
// ---------------------------------------------------------------------------

export const PROGRESS_STEPS = {
  /** Progress percentage ranges for each step */
  STEPS: [
    { id: "inlezen", name: "Inlezen", startPct: 0, endPct: 20 },
    { id: "analyseren", name: "Analyseren", startPct: 20, endPct: 60 },
    { id: "clusteren", name: "Clusteren", startPct: 60, endPct: 90 },
    { id: "resultaten", name: "Resultaten", startPct: 90, endPct: 100 },
  ],
} as const;

// ---------------------------------------------------------------------------
// File Upload Configuration
// ---------------------------------------------------------------------------

export const UPLOAD_CONFIG = {
  /** Accepted file types for policy files */
  POLICY_FILE_TYPES: [".xlsx", ".xls", ".csv"],

  /** Accepted file types for conditions files */
  CONDITIONS_FILE_TYPES: [".pdf", ".docx", ".txt"],

  /** Accepted file types for clause library files */
  CLAUSE_LIBRARY_FILE_TYPES: [".xlsx", ".xls", ".csv", ".pdf", ".docx"],

  /** Maximum file size in bytes (50MB) */
  MAX_FILE_SIZE_BYTES: 50 * 1024 * 1024,
} as const;
