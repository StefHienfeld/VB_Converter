/**
 * Hook for managing analysis progress state.
 */

import { useState, useCallback, useRef } from "react";
import { ProgressStep } from "@/types/job";
import { JobStatusResponse, LogMessage } from "@/lib/api";

const DEFAULT_STEPS: ProgressStep[] = [
  { id: "1", label: "Configuratie laden", status: "pending" },
  { id: "2", label: "Bestand inlezen", status: "pending" },
  { id: "3", label: "Voorwaarden parsen", status: "pending" },
  { id: "4", label: "NLP-modellen laden", status: "pending" },
  { id: "5", label: "Data voorbereiden", status: "pending" },
  { id: "6", label: "Clusteren", status: "pending" },
  { id: "7", label: "Analyseren", status: "pending" },
  { id: "8", label: "Resultaten genereren", status: "pending" },
];

export interface UseProgressReturn {
  progressSteps: ProgressStep[];
  currentProgress: number;
  currentMessage: string;
  jobStatus: string;
  logMessages: LogMessage[];
  estimatedTimeRemaining: string | null;
  resetProgress: () => void;
  updateProgressFromBackend: (status: JobStatusResponse) => void;
  markAllCompleted: () => void;
  setInitializing: () => void;
}

/**
 * Format seconds into a human-readable string like "~3m 20s".
 */
function formatEta(seconds: number): string {
  if (seconds < 10) return "< 10s";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m > 0) return `~${m}m ${s}s`;
  return `~${s}s`;
}

export function useProgress(): UseProgressReturn {
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>(DEFAULT_STEPS);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [currentMessage, setCurrentMessage] = useState("");
  const [jobStatus, setJobStatus] = useState<string>("pending");
  const [logMessages, setLogMessages] = useState<LogMessage[]>([]);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<string | null>(null);

  // Track progress over time for ETA calculation
  const etaRef = useRef<{ startTime: number; startProgress: number } | null>(null);

  const resetProgress = useCallback(() => {
    setProgressSteps(DEFAULT_STEPS.map((step) => ({ ...step, status: "pending" })));
    setCurrentProgress(0);
    setCurrentMessage("");
    setJobStatus("pending");
    setLogMessages([]);
    setEstimatedTimeRemaining(null);
    etaRef.current = null;
  }, []);

  // Call this when analysis starts to show immediate feedback
  const setInitializing = useCallback(() => {
    setProgressSteps((prev) =>
      prev.map((step, idx) => ({
        ...step,
        status: idx === 0 ? "active" : "pending",
      }))
    );
    setCurrentMessage("Analyse wordt gestart...");
    setJobStatus("initializing");
  }, []);

  const updateProgressFromBackend = useCallback((status: JobStatusResponse) => {
    const p = status.progress ?? 0;
    const msg = status.status_message ?? "";
    const backendStatus = status.status ?? "pending";

    setCurrentProgress(p);
    setJobStatus(backendStatus);

    // Update log messages from backend
    if (status.log_messages && status.log_messages.length > 0) {
      setLogMessages(status.log_messages);
    }

    // ETA calculation: start tracking when progress first exceeds 10%
    if (p >= 10 && p < 100) {
      if (!etaRef.current) {
        etaRef.current = { startTime: Date.now(), startProgress: p };
      } else {
        const elapsed = (Date.now() - etaRef.current.startTime) / 1000;
        const progressMade = p - etaRef.current.startProgress;
        if (progressMade > 2 && elapsed > 3) {
          const rate = progressMade / elapsed; // % per second
          const remaining = (100 - p) / rate;
          setEstimatedTimeRemaining(formatEta(remaining));
        }
      }
    } else if (p >= 100) {
      setEstimatedTimeRemaining(null);
    }

    // Provide helpful message based on status if no message from backend
    if (!msg && backendStatus === "pending") {
      setCurrentMessage("Wachten op verwerking door server...");
    } else if (!msg && backendStatus === "running" && p === 0) {
      setCurrentMessage("Analyse wordt geïnitialiseerd...");
    } else {
      setCurrentMessage(msg);
    }

    // Progress → step mapping (matches backend orchestrator phases):
    // Phase 1: Configuratie (0-5%)
    // Phase 2: Bestand inlezen (5-10%)
    // Phase 3: Voorwaarden parsen (10-12%)
    // Phase 4: NLP-modellen laden (12-22%)
    // Phase 5: Data voorbereiden (22-25%)
    // Phase 6: Clusteren (25-50%)
    // Phase 7: Analyseren (50-90%)
    // Phase 8: Resultaten genereren (90-100%)
    const thresholds = [5, 10, 12, 22, 25, 50, 90, 100];

    setProgressSteps((prev) =>
      prev.map((step, idx) => {
        // Als job nog pending of net running is, eerste stap actief
        if (backendStatus === "pending" || (backendStatus === "running" && p === 0)) {
          return idx === 0
            ? { ...step, status: "active" as const }
            : { ...step, status: "pending" as const };
        }

        const completedAt = thresholds[idx];
        const activeAt = idx === 0 ? 0 : thresholds[idx - 1];

        if (p >= completedAt) return { ...step, status: "completed" as const };
        if (p >= activeAt) return { ...step, status: "active" as const };
        return { ...step, status: "pending" as const };
      })
    );
  }, []);

  const markAllCompleted = useCallback(() => {
    setProgressSteps((prev) =>
      prev.map((step) => ({ ...step, status: "completed" as const }))
    );
    setJobStatus("completed");
    setEstimatedTimeRemaining(null);
  }, []);

  return {
    progressSteps,
    currentProgress,
    currentMessage,
    jobStatus,
    logMessages,
    estimatedTimeRemaining,
    resetProgress,
    updateProgressFromBackend,
    markAllCompleted,
    setInitializing,
  };
}
