/**
 * Hook for managing file upload state.
 */

import { useState, useCallback } from "react";
import { FileUploadState, DEFAULT_FILE_STATE } from "@/types/settings";
import { useToast } from "@/hooks/use-toast";

export interface UseFileUploadReturn extends FileUploadState {
  handlePolicyUpload: (files: File[]) => Promise<void>;
  handleConditionsUpload: (files: File[]) => void;
  handleClauseLibraryUpload: (files: File[]) => void;
  setExtraInstruction: (value: string) => void;
  resetFiles: () => void;
}

export function useFileUpload(): UseFileUploadReturn {
  const { toast } = useToast();
  const [policyFile, setPolicyFile] = useState<File | null>(DEFAULT_FILE_STATE.policyFile);
  const [conditionsFiles, setConditionsFiles] = useState<File[]>(DEFAULT_FILE_STATE.conditionsFiles);
  const [clauseLibraryFiles, setClauseLibraryFiles] = useState<File[]>(DEFAULT_FILE_STATE.clauseLibraryFiles);
  const [extraInstruction, setExtraInstruction] = useState(DEFAULT_FILE_STATE.extraInstruction);
  const [estimatedRows, setEstimatedRows] = useState(DEFAULT_FILE_STATE.estimatedRows);

  const handlePolicyUpload = useCallback(
    async (files: File[]) => {
      const file = files[0];
      setPolicyFile(file);

      // Estimate row count for time prediction
      try {
        const text = await file.text();
        let rows = 0;

        if (file.name.endsWith(".csv")) {
          rows = text.split("\n").filter((line) => line.trim()).length - 1;
        } else if (file.name.endsWith(".xlsx") || file.name.endsWith(".xls")) {
          rows = Math.floor(file.size / 200);
        }

        setEstimatedRows(Math.max(0, rows));
      } catch {
        setEstimatedRows(Math.floor(file.size / 200));
      }

      toast({
        title: "Bestand geupload",
        description: `${file.name} is succesvol toegevoegd.`,
      });
    },
    [toast]
  );

  const handleConditionsUpload = useCallback(
    (files: File[]) => {
      setConditionsFiles((prev) => {
        const existingNames = new Set(prev.map((f) => f.name + f.size));
        const newFiles = files.filter((f) => !existingNames.has(f.name + f.size));
        return [...prev, ...newFiles];
      });
      if (files.length > 0) {
        toast({
          title: "Voorwaarden geupload",
          description:
            files.length === 1
              ? `${files[0].name} is toegevoegd.`
              : `${files.length} bestanden zijn toegevoegd.`,
        });
      }
    },
    [toast]
  );

  const handleClauseLibraryUpload = useCallback(
    (files: File[]) => {
      setClauseLibraryFiles((prev) => {
        const existingNames = new Set(prev.map((f) => f.name + f.size));
        const newFiles = files.filter((f) => !existingNames.has(f.name + f.size));
        return [...prev, ...newFiles];
      });
      if (files.length > 0) {
        toast({
          title: "Clausulebibliotheek geupload",
          description:
            files.length === 1
              ? `${files[0].name} is toegevoegd.`
              : `${files.length} bestanden zijn toegevoegd.`,
        });
      }
    },
    [toast]
  );

  const resetFiles = useCallback(() => {
    setPolicyFile(null);
    setConditionsFiles([]);
    setClauseLibraryFiles([]);
    setExtraInstruction("");
    setEstimatedRows(0);
  }, []);

  return {
    policyFile,
    conditionsFiles,
    clauseLibraryFiles,
    extraInstruction,
    estimatedRows,
    handlePolicyUpload,
    handleConditionsUpload,
    handleClauseLibraryUpload,
    setExtraInstruction,
    resetFiles,
  };
}
