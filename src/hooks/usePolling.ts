/**
 * Hook for polling job status from the backend.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { getJobStatus, getResults, JobStatusResponse, AnalysisResultsResponse } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const MAX_POLLING_TIME = 600000; // 10 minutes
const POLL_INTERVAL = 1500; // 1.5 seconds

export interface UsePollingOptions {
  onProgress?: (status: JobStatusResponse) => void;
  onComplete?: (results: AnalysisResultsResponse) => void;
  onError?: (error: Error) => void;
}

export interface UsePollingReturn {
  isPolling: boolean;
  startPolling: (jobId: string) => void;
  stopPolling: () => void;
  stats: JobStatusResponse["stats"] | null;
}

export function usePolling(options: UsePollingOptions = {}): UsePollingReturn {
  const { toast } = useToast();
  const { onProgress, onComplete, onError } = options;

  const [isPolling, setIsPolling] = useState(false);
  const [stats, setStats] = useState<JobStatusResponse["stats"] | null>(null);

  const pollingStartTimeRef = useRef<number | null>(null);
  const activeJobIdRef = useRef<string | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
    pollingStartTimeRef.current = null;
    activeJobIdRef.current = null;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const poll = useCallback(
    async (jobId: string) => {
      // Check if polling was stopped
      if (activeJobIdRef.current !== jobId) {
        return;
      }

      try {
        // Check for timeout
        if (
          pollingStartTimeRef.current &&
          Date.now() - pollingStartTimeRef.current > MAX_POLLING_TIME
        ) {
          stopPolling();
          const error = new Error(
            "De analyse duurt te lang. Mogelijk is de server bezig met het downloaden van ML modellen. Probeer het later opnieuw."
          );
          toast({
            title: "Analyse time-out",
            description: error.message,
            variant: "destructive",
          });
          onError?.(error);
          return;
        }

        const status = await getJobStatus(jobId);
        onProgress?.(status);
        setStats(status.stats ?? null);

        if (status.status === "completed") {
          const results = await getResults(jobId);
          stopPolling();
          toast({
            title: "Analyse voltooid",
            description: "De resultaten zijn klaar.",
          });
          onComplete?.(results);
        } else if (status.status === "failed") {
          stopPolling();
          const error = new Error(
            status.error || "Er is een fout opgetreden tijdens de analyse."
          );
          toast({
            title: "Analyse mislukt",
            description: error.message,
            variant: "destructive",
          });
          onError?.(error);
        } else {
          // Continue polling
          timeoutRef.current = setTimeout(() => poll(jobId), POLL_INTERVAL);
        }
      } catch (error: unknown) {
        stopPolling();
        const err = error instanceof Error ? error : new Error("Kon de status niet ophalen.");
        toast({
          title: "Fout bij ophalen status",
          description: err.message,
          variant: "destructive",
        });
        onError?.(err);
      }
    },
    [toast, onProgress, onComplete, onError, stopPolling]
  );

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling(); // Clear any existing polling
      setIsPolling(true);
      pollingStartTimeRef.current = Date.now();
      activeJobIdRef.current = jobId;
      poll(jobId);
    },
    [poll, stopPolling]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return {
    isPolling,
    startPolling,
    stopPolling,
    stats,
  };
}
