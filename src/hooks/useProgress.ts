/**
 * Hook for managing analysis progress state.
 */

import { useState, useCallback, useRef } from "react";
import { ProgressStep } from "@/types/job";
import { JobStatusResponse, LogMessage } from "@/lib/api";

const DEFAULT_STEPS: ProgressStep[] = [
  { id: "1", label: "Bestanden inlezen", status: "pending" },
  { id: "2", label: "Clusteren", status: "pending" },
  { id: "3", label: "Analyseren", status: "pending" },
  { id: "4", label: "Resultaten genereren", status: "pending" },
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

    setProgressSteps((prev) =>
      prev.map((step, idx) => {
        // Als job nog pending of net running is, eerste stap actief
        if (backendStatus === "pending" || (backendStatus === "running" && p === 0)) {
          return idx === 0
            ? { ...step, status: "active" as const }
            : { ...step, status: "pending" as const };
        }

        if (p >= 95) {
          return { ...step, status: "completed" as const };
        }

        // Stap 1: Bestanden inlezen (0-25%)
        if (idx === 0) {
          if (p >= 25) return { ...step, status: "completed" as const };
          if (p >= 0) return { ...step, status: "active" as const };
        }

        // Stap 2: Clusteren (25-50%) - Backend doet dit eerst!
        if (idx === 1) {
          if (p >= 50) return { ...step, status: "completed" as const };
          if (p >= 25) return { ...step, status: "active" as const };
        }

        // Stap 3: Analyseren (50-90%) - Backend doet dit na clustering
        if (idx === 2) {
          if (p >= 90) return { ...step, status: "completed" as const };
          if (p >= 50) return { ...step, status: "active" as const };
        }

        // Stap 4: Resultaten genereren (90-100%)
        if (idx === 3) {
          if (p >= 100) return { ...step, status: "completed" as const };
          if (p >= 90) return { ...step, status: "active" as const };
        }

        return step;
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
