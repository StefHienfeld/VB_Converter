import { useState, useCallback, useEffect } from "react";
import { FileStack, TrendingDown, Network, Download, Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FloatingHeader } from "@/components/layout/FloatingHeader";
import { FileDropZone } from "@/components/upload/FileDropZone";
import { ExtraInstructionInput } from "@/components/upload/ExtraInstructionInput";
import { MetricWidget } from "@/components/metrics/MetricWidget";
import { AnalysisProgress } from "@/components/analysis/AnalysisProgress";
import { ResultsTable } from "@/components/results/ResultsTable";
import { SettingsDrawer } from "@/components/settings/SettingsDrawer";
import { HelpDialog } from "@/components/help/HelpDialog";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  startAnalysis,
  getJobStatus,
  getResults,
  downloadReport,
  JobStatusResponse,
} from "@/lib/api";
import { AnalysisResultRow } from "@/types/analysis";

const Index = () => {
  const { toast } = useToast();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);

  const [policyFile, setPolicyFile] = useState<File | null>(null);
  const [conditionsFiles, setConditionsFiles] = useState<File[]>([]);
  const [clauseLibraryFile, setClauseLibraryFile] = useState<File | null>(null);
  const [extraInstruction, setExtraInstruction] = useState("");

  const [settings, setSettings] = useState({
    clusterAccuracy: 90,
    minFrequency: 20,
    windowSize: 200,
    aiEnabled: true,
  });

  const [progressSteps, setProgressSteps] = useState<
    { id: string; label: string; status: "pending" | "active" | "completed" }[]
  >([
    { id: "1", label: "Bestanden inlezen", status: "pending" },
    { id: "2", label: "Analyseren", status: "pending" },
    { id: "3", label: "Clusteren", status: "pending" },
    { id: "4", label: "Resultaten genereren", status: "pending" },
  ]);

  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<AnalysisResultRow[]>([]);
  const [stats, setStats] = useState<JobStatusResponse["stats"] | null>(null);
  const [inputView, setInputView] = useState<"full" | "compact">("full");

  const handlePolicyUpload = useCallback(
    (files: File[]) => {
      const file = files[0];
      setPolicyFile(file);
      toast({
        title: "Bestand geüpload",
        description: `${file.name} is succesvol toegevoegd.`,
      });
    },
    [toast],
  );

  const handleConditionsUpload = useCallback(
    (files: File[]) => {
      setConditionsFiles((prev) => {
        // Combine existing files with new files, avoiding duplicates
        const existingNames = new Set(prev.map(f => f.name + f.size));
        const newFiles = files.filter(f => !existingNames.has(f.name + f.size));
        return [...prev, ...newFiles];
      });
      if (files.length > 0) {
        toast({
          title: "Voorwaarden geüpload",
          description: files.length === 1 
            ? `${files[0].name} is toegevoegd.`
            : `${files.length} bestanden zijn toegevoegd.`,
        });
      }
    },
    [toast],
  );

  const handleClauseLibraryUpload = useCallback(
    (files: File[]) => {
      const file = files[0];
      setClauseLibraryFile(file);
      toast({
        title: "Clausulebibliotheek geüpload",
        description: `${file.name} is toegevoegd.`,
      });
    },
    [toast],
  );

  const resetProgress = useCallback(() => {
    setProgressSteps((prev) =>
      prev.map((step) => ({
        ...step,
        status: "pending",
      })),
    );
  }, []);

  const updateProgressFromBackend = useCallback((status: JobStatusResponse) => {
    const p = status.progress ?? 0;
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
      }),
    );
  }, []);

  const pollStatus = useCallback(
    async (currentJobId: string) => {
      try {
        const status = await getJobStatus(currentJobId);
        updateProgressFromBackend(status);
        setStats(status.stats ?? null);

        if (status.status === "completed") {
          const res = await getResults(currentJobId);
          setResults(res.results);
          setAnalysisComplete(true);
          setIsAnalyzing(false);
          setProgressSteps((prev) =>
            prev.map((step) => ({ ...step, status: "completed" })),
          );
          toast({
            title: "Analyse voltooid",
            description: "De resultaten zijn klaar.",
          });
        } else if (status.status === "failed") {
          setIsAnalyzing(false);
          toast({
            title: "Analyse mislukt",
            description: status.error || "Er is een fout opgetreden tijdens de analyse.",
            variant: "destructive",
          });
        } else {
          setTimeout(() => pollStatus(currentJobId), 1500);
        }
      } catch (error: any) {
        setIsAnalyzing(false);
        toast({
          title: "Fout bij ophalen status",
          description: error?.message || "Kon de status niet ophalen.",
          variant: "destructive",
        });
      }
    },
    [toast, updateProgressFromBackend],
  );

  const handleNewAnalysis = useCallback(() => {
    setInputView("full");
  }, []);

  const handleStartAnalysis = useCallback(async () => {
    if (!policyFile) {
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
      resetProgress();

      setInputView("compact");

      const res = await startAnalysis({
        policyFile,
        conditionsFiles,
        clauseLibraryFile,
        settings,
        extraInstruction,
      });

      setJobId(res.job_id);
      pollStatus(res.job_id);
    } catch (error: any) {
      setIsAnalyzing(false);
      toast({
        title: "Analyse starten mislukt",
        description: error?.message || "Er is een fout opgetreden bij het starten.",
        variant: "destructive",
      });
    }
  }, [
    policyFile,
    conditionsFiles,
    clauseLibraryFile,
    settings,
    extraInstruction,
    toast,
    resetProgress,
    pollStatus,
  ]);

  const handleDownload = useCallback(async () => {
    if (!jobId) return;
    try {
      await downloadReport(jobId);
      toast({
        title: "Download gestart",
        description: "Uw Excel rapport wordt gedownload...",
      });
    } catch (error: any) {
      toast({
        title: "Download mislukt",
        description: error?.message || "Kon het rapport niet downloaden.",
        variant: "destructive",
      });
    }
  }, [jobId, toast]);

  const canStartAnalysis = !!policyFile && !isAnalyzing;

  useEffect(() => {
    setAnalysisComplete(false);
    setResults([]);
    setStats(null);
    setJobId(null);
    resetProgress();
  }, [policyFile, resetProgress]);

  return (
    <div className="min-h-screen bg-background">
      <FloatingHeader
        onSettingsClick={() => setSettingsOpen(true)}
        onHelpClick={() => setHelpOpen(true)}
      />

      <main className="container max-w-7xl mx-auto px-4 pb-12">
        {/* Input Section - Full Width */}
        <div className="transition-all duration-700 ease-in-out">
          <div className={cn(
            "space-y-6 transition-all duration-700 ease-in-out origin-top",
            inputView === "compact" 
              ? "scale-[0.6] opacity-40 grayscale pointer-events-none mb-[-180px]" 
              : "scale-100 opacity-100 mb-8"
          )}>
            {/* Upload Row - 3 cards horizontal */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FileDropZone
                title="1. Polisbestand"
                description="Sleep Excel/CSV bestand"
                accept=".xlsx,.xls,.csv"
                onFileSelect={handlePolicyUpload}
                status={policyFile ? "success" : "idle"}
                uploadedFile={
                  policyFile ? { name: policyFile.name, size: policyFile.size } : null
                }
                className="animate-fade-up"
              />

              <FileDropZone
                title="2. Voorwaarden (optioneel)"
                description="Sleep PDF/TXT/DOCX"
                accept=".pdf,.txt,.docx"
                onFileSelect={handleConditionsUpload}
                status={conditionsFiles.length > 0 ? "success" : "idle"}
                multiple={true}
                uploadedFiles={
                  conditionsFiles.length > 0
                    ? conditionsFiles.map(f => ({ name: f.name, size: f.size }))
                    : undefined
                }
                className="animate-fade-up animation-delay-100"
              />

              <FileDropZone
                title="3. Clausulebibliotheek (optioneel)"
                description="Upload bibliotheek"
                accept=".xlsx,.xls,.csv,.pdf,.docx"
                onFileSelect={handleClauseLibraryUpload}
                status={clauseLibraryFile ? "success" : "idle"}
                uploadedFile={
                  clauseLibraryFile
                    ? { name: clauseLibraryFile.name, size: clauseLibraryFile.size }
                    : null
                }
                className="animate-fade-up animation-delay-150"
              />
            </div>

            <ExtraInstructionInput
              value={extraInstruction}
              onChange={setExtraInstruction}
              className="animate-fade-up animation-delay-200"
            />
          </div>

          <div className="flex flex-col items-center gap-4 mb-8 relative z-10">
            <Button
              onClick={inputView === "compact" ? handleNewAnalysis : handleStartAnalysis}
              disabled={!canStartAnalysis && inputView !== "compact"}
              className={cn(
                "btn-primary-cta w-full md:w-auto md:min-w-[200px] h-14 text-sm rounded-xl",
                "animate-fade-up animation-delay-300"
              )}
            >
              {isAnalyzing ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                inputView === "compact" ? (
                  "Nieuwe Analyse"
                ) : (
                  <>
                    <Play className="w-5 h-5 mr-2" />
                    Start Analyse
                  </>
                )
              )}
            </Button>

            {analysisComplete && jobId && (
              <Button
                onClick={handleDownload}
                className={cn(
                  "w-full md:w-auto md:min-w-[200px] h-14 text-sm rounded-xl font-bold uppercase tracking-wider",
                  "bg-[#1D6F42] hover:bg-[#155431] text-white shadow-lg hover:shadow-xl transition-all",
                  "animate-fade-up"
                )}
              >
                <Download className="w-5 h-5 mr-2" />
                Download Excel Output
              </Button>
            )}
          </div>
        </div>

        {/* Output Section */}
        {(isAnalyzing || analysisComplete) && (
          <div className="space-y-6">
            {/* Metrics Row */}
            {analysisComplete && stats && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-up">
                <MetricWidget
                  icon={FileStack}
                  label="Verwerkte Rijen"
                  value={stats.total_rows ?? 0}
                  subValue={
                    stats.total_rows
                      ? `${stats.total_rows} rijen geanalyseerd`
                      : undefined
                  }
                  variant="default"
                />
                <MetricWidget
                  icon={TrendingDown}
                  label="Reductie"
                  value={`${stats.reduction_percentage ?? 0}%`}
                  subValue={
                    stats.total_rows && stats.unique_clusters
                      ? `${stats.total_rows - stats.unique_clusters} rijen minder`
                      : undefined
                  }
                  variant="success"
                />
                <MetricWidget
                  icon={Network}
                  label="Clusters"
                  value={stats.unique_clusters ?? 0}
                  subValue="unieke groepen"
                  variant="primary"
                />
              </div>
            )}

            {/* Progress & Results */}
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,280px)_minmax(0,1fr)] gap-4 items-start">
              <AnalysisProgress
                steps={progressSteps}
                className="order-2 lg:order-1 animate-fade-up animation-delay-200"
              >
                {analysisComplete && (
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={handleDownload}
                    disabled={!analysisComplete || !jobId}
                    className={cn(
                      "w-full rounded-xl h-12 text-sm font-medium border-primary/20 hover:bg-primary/5",
                      "animate-fade-up"
                    )}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download Rapport
                  </Button>
                )}
              </AnalysisProgress>

              <div className="space-y-4 order-1 lg:order-2">
                {analysisComplete && (
                  <>
                    <ResultsTable
                      data={results.slice(0, 10)}
                      className="animate-fade-up animation-delay-200"
                    />
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Dialogs */}
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSettingsChange={(newSettings) =>
          setSettings((prev) => ({ ...prev, ...newSettings }))
        }
      />

      <HelpDialog open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  );
};

export default Index;
