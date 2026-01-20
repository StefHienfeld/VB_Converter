import { AnalysisResultRow } from "@/types/analysis";
import { API_CONFIG, UI_CONFIG } from "./constants";

const { BASE_URL: API_BASE_URL, DEBUG, TIMEOUT_MS: API_TIMEOUT_MS } = API_CONFIG;

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
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/status/${jobId}`);

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
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/results/${jobId}`);

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
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/report/${jobId}`);

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
