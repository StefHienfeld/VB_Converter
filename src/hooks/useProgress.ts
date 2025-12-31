/**
 * Hook for managing analysis progress state.
 */

import { useState, useCallback } from "react";
import { ProgressStep } from "@/types/job";
import { JobStatusResponse } from "@/lib/api";

const DEFAULT_STEPS: ProgressStep[] = [
  { id: "1", label: "Bestanden inlezen", status: "pending" },
  { id: "2", label: "Analyseren", status: "pending" },
  { id: "3", label: "Clusteren", status: "pending" },
  { id: "4", label: "Resultaten genereren", status: "pending" },
];

export interface UseProgressReturn {
  progressSteps: ProgressStep[];
  currentProgress: number;
  currentMessage: string;
  resetProgress: () => void;
  updateProgressFromBackend: (status: JobStatusResponse) => void;
  markAllCompleted: () => void;
}

export function useProgress(): UseProgressReturn {
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>(DEFAULT_STEPS);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [currentMessage, setCurrentMessage] = useState("");

  const resetProgress = useCallback(() => {
    setProgressSteps(DEFAULT_STEPS.map((step) => ({ ...step, status: "pending" })));
    setCurrentProgress(0);
    setCurrentMessage("");
  }, []);

  const updateProgressFromBackend = useCallback((status: JobStatusResponse) => {
    const p = status.progress ?? 0;
    const msg = status.status_message ?? "";

    setCurrentProgress(p);
    setCurrentMessage(msg);

    setProgressSteps((prev) =>
      prev.map((step, idx) => {
        if (p >= 95) {
          return { ...step, status: "completed" };
        }
        if (idx === 0 && p > 0 && p < 20) return { ...step, status: "active" };
        if (idx === 0 && p >= 20) return { ...step, status: "completed" };
        if (idx === 1 && p >= 20 && p < 60) return { ...step, status: "active" };
        if (idx === 1 && p >= 60) return { ...step, status: "completed" };
        if (idx === 2 && p >= 60 && p < 90) return { ...step, status: "active" };
        if (idx === 2 && p >= 90) return { ...step, status: "completed" };
        if (idx === 3 && p >= 95) return { ...step, status: "active" };
        return step;
      })
    );
  }, []);

  const markAllCompleted = useCallback(() => {
    setProgressSteps((prev) =>
      prev.map((step) => ({ ...step, status: "completed" }))
    );
  }, []);

  return {
    progressSteps,
    currentProgress,
    currentMessage,
    resetProgress,
    updateProgressFromBackend,
    markAllCompleted,
  };
}
