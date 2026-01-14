/**
 * Main orchestration hook for analysis workflow.
 * Combines file upload, polling, and progress management.
 */

import { useState, useCallback, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { useFileUpload } from "@/hooks/useFileUpload";
import { usePolling } from "@/hooks/usePolling";
import { useProgress } from "@/hooks/useProgress";
import { AnalysisSettings, DEFAULT_SETTINGS } from "@/types/settings";
import { AnalysisResultRow } from "@/types/analysis";
import { startAnalysis, downloadReport, JobStatusResponse, AnalysisResultsResponse } from "@/lib/api";

export type InputView = "full" | "compact";

export interface UseAnalysisReturn {
  // File upload state
  policyFile: File | null;
  conditionsFiles: File[];
  clauseLibraryFiles: File[];
  referenceFile: File | null;
  extraInstruction: string;
  estimatedRows: number;
  handlePolicyUpload: (files: File[]) => Promise<void>;
  handleConditionsUpload: (files: File[]) => void;
  handleClauseLibraryUpload: (files: File[]) => void;
  handleReferenceUpload: (files: File[]) => void;
  setExtraInstruction: (value: string) => void;

  // Settings
  settings: AnalysisSettings;
  setSettings: React.Dispatch<React.SetStateAction<AnalysisSettings>>;

  // Analysis state
  isAnalyzing: boolean;
  analysisComplete: boolean;
  jobId: string | null;
  results: AnalysisResultRow[];
  stats: JobStatusResponse["stats"] | null;

  // Progress state
  progressSteps: { id: string; label: string; status: "pending" | "active" | "completed" }[];
  currentProgress: number;
  currentMessage: string;
  jobStatus: string;
  startTime: number | null;

  // UI state
  inputView: InputView;
  canStartAnalysis: boolean;

  // Actions
  handleStartAnalysis: () => Promise<void>;
  handleCancelAnalysis: () => void;
  handleNewAnalysis: () => void;
  handleDownload: () => Promise<void>;
}

export function useAnalysis(): UseAnalysisReturn {
  const { toast } = useToast();

  // File upload hook
  const fileUpload = useFileUpload();

  // Progress hook
  const progress = useProgress();

  // Analysis state
  const [settings, setSettings] = useState<AnalysisSettings>(DEFAULT_SETTINGS);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResultRow[]>([]);
  const [inputView, setInputView] = useState<InputView>("full");
  const [startTime, setStartTime] = useState<number | null>(null);

  // Polling hook with callbacks
  const polling = usePolling({
    onProgress: (status: JobStatusResponse) => {
      progress.updateProgressFromBackend(status);
    },
    onComplete: (response: AnalysisResultsResponse) => {
      setResults(response.results);
      setAnalysisComplete(true);
      setIsAnalyzing(false);
      progress.markAllCompleted();
    },
    onError: () => {
      setIsAnalyzing(false);
    },
  });

  const canStartAnalysis = !!fileUpload.policyFile && !isAnalyzing;

  const handleStartAnalysis = useCallback(async () => {
    if (!fileUpload.policyFile) {
      toast({
        title: "Polisbestand ontbreekt",
        description: "Upload eerst het polisbestand om te starten.",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsAnalyzing(true);
      setAnalysisComplete(false);
      setResults([]);
      progress.resetProgress();
      setInputView("compact");
      
      // Set start time and show immediate feedback
      setStartTime(Date.now());
      progress.setInitializing();

      const res = await startAnalysis({
        policyFile: fileUpload.policyFile,
        conditionsFiles: fileUpload.conditionsFiles,
        clauseLibraryFiles: fileUpload.clauseLibraryFiles,
        referenceFile: fileUpload.referenceFile,
        settings,
        extraInstruction: fileUpload.extraInstruction,
      });

      setJobId(res.job_id);
      polling.startPolling(res.job_id);
    } catch (error: unknown) {
      setIsAnalyzing(false);
      setStartTime(null);
      const err = error instanceof Error ? error : new Error("Er is een fout opgetreden bij het starten.");
      toast({
        title: "Analyse starten mislukt",
        description: err.message,
        variant: "destructive",
      });
    }
  }, [fileUpload, settings, toast, progress, polling]);

  const handleCancelAnalysis = useCallback(() => {
    polling.stopPolling();
    setIsAnalyzing(false);
    setInputView("full");
    setStartTime(null);
    toast({
      title: "Analyse geannuleerd",
      description: "De analyse is gestopt. U kunt een nieuwe analyse starten.",
    });
  }, [polling, toast]);

  const handleNewAnalysis = useCallback(() => {
    setInputView("full");
  }, []);

  const handleDownload = useCallback(async () => {
    if (!jobId) return;
    try {
      await downloadReport(jobId);
      toast({
        title: "Download gestart",
        description: "Uw Excel rapport wordt gedownload...",
      });
    } catch (error: unknown) {
      const err = error instanceof Error ? error : new Error("Kon het rapport niet downloaden.");
      toast({
        title: "Download mislukt",
        description: err.message,
        variant: "destructive",
      });
    }
  }, [jobId, toast]);

  // Reset analysis state when policy file changes
  useEffect(() => {
    setAnalysisComplete(false);
    setResults([]);
    setJobId(null);
    setStartTime(null);
    progress.resetProgress();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileUpload.policyFile]); // Alleen resetten bij nieuw bestand

  return {
    // File upload state
    policyFile: fileUpload.policyFile,
    conditionsFiles: fileUpload.conditionsFiles,
    clauseLibraryFiles: fileUpload.clauseLibraryFiles,
    referenceFile: fileUpload.referenceFile,
    extraInstruction: fileUpload.extraInstruction,
    estimatedRows: fileUpload.estimatedRows,
    handlePolicyUpload: fileUpload.handlePolicyUpload,
    handleConditionsUpload: fileUpload.handleConditionsUpload,
    handleClauseLibraryUpload: fileUpload.handleClauseLibraryUpload,
    handleReferenceUpload: fileUpload.handleReferenceUpload,
    setExtraInstruction: fileUpload.setExtraInstruction,

    // Settings
    settings,
    setSettings,

    // Analysis state
    isAnalyzing,
    analysisComplete,
    jobId,
    results,
    stats: polling.stats,

    // Progress state
    progressSteps: progress.progressSteps,
    currentProgress: progress.currentProgress,
    currentMessage: progress.currentMessage,
    jobStatus: progress.jobStatus,
    startTime,

    // UI state
    inputView,
    canStartAnalysis,

    // Actions
    handleStartAnalysis,
    handleCancelAnalysis,
    handleNewAnalysis,
    handleDownload,
  };
}
