import { AnalysisResultRow } from "@/types/analysis";
import { API_CONFIG, UI_CONFIG } from "./constants";

const { BASE_URL: API_BASE_URL, DEBUG, TIMEOUT_MS: API_TIMEOUT_MS } = API_CONFIG;

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------

const TOKEN_KEY = "hienfeld_access_token";
const REFRESH_KEY = "hienfeld_refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Login mislukt");
  }

  const data = (await res.json()) as TokenResponse;
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function refreshAccessToken(): Promise<void> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    clearTokens();
    throw new Error("Geen refresh token beschikbaar. Log opnieuw in.");
  }

  const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    clearTokens();
    throw new Error("Sessie verlopen. Log opnieuw in.");
  }

  const data = (await res.json()) as TokenResponse;
  setTokens(data.access_token, data.refresh_token);
}

export function logout(): void {
  clearTokens();
}

export interface StartAnalysisRequest {
  policyFile: File;
  conditionsFiles?: File[];
  clauseLibraryFiles?: File[];
  referenceFile?: File | null;
  settings: {
    clusterAccuracy: number;
    minFrequency: number;
    windowSize: number;
    aiEnabled: boolean;
    analysisMode?: string;
  };
  extraInstruction?: string;
}

export interface StartAnalysisResponse {
  job_id: string;
  status: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  status_message: string;
  error?: string | null;
  stats?: {
    total_rows: number;
    unique_clusters: number;
    reduction_percentage: number;
    multi_clause_count: number;
    analysis_mode: string;
    advice_distribution: Record<string, number>;
  };
}

export interface AnalysisResultsResponse {
  job_id: string;
  status: string;
  stats: JobStatusResponse["stats"];
  results: AnalysisResultRow[];
}

/**
 * Creates a fetch request with timeout support
 */
function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = API_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  return fetch(url, {
    ...options,
    signal: controller.signal,
  }).finally(() => clearTimeout(timeoutId));
}

function buildFormData(req: StartAnalysisRequest): FormData {
  const form = new FormData();

  // Validate and append policy file
  if (!req.policyFile) {
    throw new Error("Polisbestand ontbreekt");
  }
  form.append("policy_file", req.policyFile);

  // Append conditions files
  const conditionsFiles = req.conditionsFiles || [];
  conditionsFiles.forEach((file) => {
    form.append("conditions_files", file);
  });

  // Append clause library files
  const clauseLibraryFiles = req.clauseLibraryFiles || [];
  clauseLibraryFiles.forEach((file) => {
    form.append("clause_library_files", file);
  });

  // Append reference file (optional - for yearly vs monthly comparison)
  if (req.referenceFile) {
    form.append("reference_file", req.referenceFile);
  }

  form.append("cluster_accuracy", String(req.settings.clusterAccuracy));
  form.append("min_frequency", String(req.settings.minFrequency));
  form.append("window_size", String(req.settings.windowSize));
  form.append("use_conditions", String(conditionsFiles.length > 0));
  form.append("use_window_limit", String(true));
  form.append("ai_enabled", String(req.settings.aiEnabled));
  form.append("analysis_mode", req.settings.analysisMode || "balanced");
  form.append("extra_instruction", req.extraInstruction ?? "");

  return form;
}

export async function startAnalysis(
  req: StartAnalysisRequest
): Promise<StartAnalysisResponse> {
  const formData = buildFormData(req);

  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });

    if (!res.ok) {
      const detail = await safeParseError(res);
      if (DEBUG) console.error("[API] Server error:", res.status, detail);
      throw new Error(detail || "Kon analyse niet starten");
    }

    const result = (await res.json()) as StartAnalysisResponse;
    return result;
  } catch (error) {
    // Handle timeout
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timeout - de server reageert niet");
    }
    // Enhanced error logging
    if (error instanceof TypeError && error.message.includes("fetch")) {
      if (DEBUG) {
        console.error("[API] Network error - could not reach server:", error);
        console.error("[API] Check if backend is running at:", API_BASE_URL);
      }
      throw new Error(
        `Kan geen verbinding maken met de server (${API_BASE_URL}). ` +
        "Controleer of de backend draait."
      );
    }
    throw error;
  }
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/status/${jobId}`, {
    headers: authHeaders(),
  });

  if (res.status === 404) {
    throw new Error("Job niet gevonden (404) - server mogelijk herstart");
  }

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Status ophalen mislukt");
  }

  return (await res.json()) as JobStatusResponse;
}

export async function getResults(jobId: string): Promise<AnalysisResultsResponse> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/results/${jobId}`, {
    headers: authHeaders(),
  });

  if (res.status === 202) {
    throw new Error("Resultaten nog niet beschikbaar");
  }

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Resultaten ophalen mislukt");
  }

  return (await res.json()) as AnalysisResultsResponse;
}

export async function downloadReport(jobId: string): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/report/${jobId}`, {
    headers: authHeaders(),
  });

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Download van rapport mislukt");
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = UI_CONFIG.DEFAULT_REPORT_FILENAME;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

async function safeParseError(res: Response): Promise<string | null> {
  try {
    const data = await res.json();
    if (data && typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    // ignore
  }
  return null;
}
