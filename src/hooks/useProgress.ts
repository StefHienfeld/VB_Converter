/**
 * Hook for managing analysis progress state.
 */

import { useState, useCallback } from "react";
import { ProgressStep } from "@/types/job";
import { JobStatusResponse } from "@/lib/api";

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
  resetProgress: () => void;
  updateProgressFromBackend: (status: JobStatusResponse) => void;
  markAllCompleted: () => void;
  setInitializing: () => void;
}

export function useProgress(): UseProgressReturn {
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>(DEFAULT_STEPS);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [currentMessage, setCurrentMessage] = useState("");
  const [jobStatus, setJobStatus] = useState<string>("pending");

  const resetProgress = useCallback(() => {
    setProgressSteps(DEFAULT_STEPS.map((step) => ({ ...step, status: "pending" })));
    setCurrentProgress(0);
    setCurrentMessage("");
    setJobStatus("pending");
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
  }, []);

  return {
    progressSteps,
    currentProgress,
    currentMessage,
    jobStatus,
    resetProgress,
    updateProgressFromBackend,
    markAllCompleted,
    setInitializing,
  };
}
