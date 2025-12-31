/**
 * Job-related types for tracking analysis job state.
 */

export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface JobState {
  jobId: string | null;
  status: JobStatus | null;
  progress: number;
  message: string;
  error: string | null;
}

export interface ProgressStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed";
}

export interface JobStats {
  unique_clusters: number;
  total_clauses: number;
  analysis_mode: string;
  semantic_status?: {
    requested: boolean;
    conditions_loaded: boolean;
    semantic_index_ready: boolean;
    hybrid_enabled: boolean;
    tfidf_trained: boolean;
    rag_indexed: boolean;
  };
  advice_distribution?: Record<string, number>;
}
