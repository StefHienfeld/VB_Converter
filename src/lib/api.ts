import { AnalysisResultRow } from "@/types/analysis";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface StartAnalysisRequest {
  policyFile: File;
  conditionsFiles?: File[];
  clauseLibraryFiles?: File[];
  settings: {
    clusterAccuracy: number;
    minFrequency: number;
    windowSize: number;
    aiEnabled: boolean;
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

function buildFormData(req: StartAnalysisRequest): FormData {
  const form = new FormData();
  form.append("policy_file", req.policyFile);
  (req.conditionsFiles || []).forEach((file) => {
    form.append("conditions_files", file);
  });
  (req.clauseLibraryFiles || []).forEach((file) => {
    form.append("clause_library_files", file);
  });

  form.append("cluster_accuracy", String(req.settings.clusterAccuracy));
  form.append("min_frequency", String(req.settings.minFrequency));
  form.append("window_size", String(req.settings.windowSize));
  form.append("use_conditions", String((req.conditionsFiles?.length ?? 0) > 0));
  form.append("use_window_limit", String(true));
  form.append("ai_enabled", String(req.settings.aiEnabled));
  form.append("extra_instruction", req.extraInstruction ?? "");

  return form;
}

export async function startAnalysis(
  req: StartAnalysisRequest
): Promise<StartAnalysisResponse> {
  const formData = buildFormData(req);

  const res = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Kon analyse niet starten");
  }

  return (await res.json()) as StartAnalysisResponse;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/status/${jobId}`);

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Status ophalen mislukt");
  }

  return (await res.json()) as JobStatusResponse;
}

export async function getResults(jobId: string): Promise<AnalysisResultsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/results/${jobId}`);

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
  const res = await fetch(`${API_BASE_URL}/api/report/${jobId}`);

  if (!res.ok) {
    const detail = await safeParseError(res);
    throw new Error(detail || "Download van rapport mislukt");
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "Hienfeld_Analyse.xlsx";
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


