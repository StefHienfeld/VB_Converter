/**
 * Hook for polling job status from the backend.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { getJobStatus, getResults, JobStatusResponse, AnalysisResultsResponse } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { POLLING_CONFIG } from "@/lib/constants";

// Extract polling configuration
const { INTERVAL_MS: POLL_INTERVAL, MAX_RETRIES, BACKOFF_MULTIPLIER } = POLLING_CONFIG;

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

  const activeJobIdRef = useRef<string | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef<number>(0);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
    activeJobIdRef.current = null;
    retryCountRef.current = 0;
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
        const status = await getJobStatus(jobId);
        retryCountRef.current = 0; // Reset retry count on success
        onProgress?.(status);
        setStats(status.stats ?? null);

        // Geen timeout - laat de analyse doorlopen totdat backend completed/failed retourneert

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
        const err = error instanceof Error ? error : new Error("Kon de status niet ophalen.");
        
        // Specifieke handling voor 404 (job niet meer beschikbaar) - geen retry
        const is404 = err.message.includes("404") || err.message.includes("niet gevonden");
        
        if (is404) {
          stopPolling();
          toast({
            title: "Analyse onderbroken",
            description: "De server is mogelijk herstart. Start de analyse opnieuw.",
            variant: "destructive",
          });
          onError?.(err);
          return;
        }
        
        // Retry bij netwerk/tijdelijke errors
        retryCountRef.current += 1;
        if (retryCountRef.current <= MAX_RETRIES) {
          console.warn(`[Polling] Retry ${retryCountRef.current}/${MAX_RETRIES} na error:`, err.message);
          // Wacht iets langer bij retry (exponential backoff)
          const retryDelay = POLL_INTERVAL * Math.pow(BACKOFF_MULTIPLIER, retryCountRef.current - 1);
          timeoutRef.current = setTimeout(() => poll(jobId), retryDelay);
          return;
        }
        
        // Max retries bereikt, stop polling
        stopPolling();
        toast({
          title: "Fout bij ophalen status",
          description: `${err.message} (na ${MAX_RETRIES} pogingen)`,
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
