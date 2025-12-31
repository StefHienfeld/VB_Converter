/**
 * Settings-related types for analysis configuration.
 */

export type AnalysisMode = "fast" | "balanced" | "accurate";

export interface AnalysisSettings {
  clusterAccuracy: number;
  minFrequency: number;
  windowSize: number;
  aiEnabled: boolean;
  analysisMode: AnalysisMode;
}

export interface FileUploadState {
  policyFile: File | null;
  conditionsFiles: File[];
  clauseLibraryFiles: File[];
  extraInstruction: string;
  estimatedRows: number;
}

export const DEFAULT_SETTINGS: AnalysisSettings = {
  clusterAccuracy: 90,
  minFrequency: 20,
  windowSize: 200,
  aiEnabled: false,
  analysisMode: "balanced",
};

export const DEFAULT_FILE_STATE: FileUploadState = {
  policyFile: null,
  conditionsFiles: [],
  clauseLibraryFiles: [],
  extraInstruction: "",
  estimatedRows: 0,
};
