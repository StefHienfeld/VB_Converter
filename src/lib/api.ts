import { AnalysisResultRow } from "@/types/analysis";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

function buildFormData(req: StartAnalysisRequest): FormData {
  const form = new FormData();
  
  // Validate and append policy file
  if (!req.policyFile) {
    throw new Error("Polisbestand ontbreekt");
  }
  console.log("[FormData] Adding policy file:", req.policyFile.name, req.policyFile.size, "bytes");
  form.append("policy_file", req.policyFile);
  
  // Append conditions files
  const conditionsFiles = req.conditionsFiles || [];
  console.log("[FormData] Adding", conditionsFiles.length, "conditions files");
  conditionsFiles.forEach((file, idx) => {
    console.log(`[FormData]   ${idx + 1}. ${file.name} (${file.size} bytes)`);
    form.append("conditions_files", file);
  });
  
  // Append clause library files
  const clauseLibraryFiles = req.clauseLibraryFiles || [];
  console.log("[FormData] Adding", clauseLibraryFiles.length, "clause library files");
  clauseLibraryFiles.forEach((file, idx) => {
    console.log(`[FormData]   ${idx + 1}. ${file.name} (${file.size} bytes)`);
    form.append("clause_library_files", file);
  });

  // Append reference file (optional - for yearly vs monthly comparison)
  if (req.referenceFile) {
    console.log("[FormData] Adding reference file:", req.referenceFile.name, req.referenceFile.size, "bytes");
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

  console.log("[FormData] FormData built successfully");
  return form;
}

export async function startAnalysis(
  req: StartAnalysisRequest
): Promise<StartAnalysisResponse> {
  const formData = buildFormData(req);

  // Log upload details for debugging
  console.log("[API] Starting analysis with:", {
    policyFile: req.policyFile?.name,
    policyFileSize: req.policyFile?.size,
    conditionsFilesCount: req.conditionsFiles?.length ?? 0,
    clauseLibraryFilesCount: req.clauseLibraryFiles?.length ?? 0,
    apiUrl: `${API_BASE_URL}/api/analyze`
  });

  try {
    const res = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const detail = await safeParseError(res);
      console.error("[API] Server error:", res.status, detail);
      throw new Error(detail || "Kon analyse niet starten");
    }

    const result = (await res.json()) as StartAnalysisResponse;
    console.log("[API] Analysis started:", result);
    return result;
  } catch (error) {
    // Enhanced error logging
    if (error instanceof TypeError && error.message.includes("fetch")) {
      console.error("[API] Network error - could not reach server:", error);
      console.error("[API] Check if backend is running at:", API_BASE_URL);
      throw new Error(
        `Kan geen verbinding maken met de server (${API_BASE_URL}). ` +
        "Controleer of de backend draait."
      );
    }
    throw error;
  }
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


