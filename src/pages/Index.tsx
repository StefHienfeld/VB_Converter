import { useState, useCallback } from "react";
import { FileStack, TrendingDown, Network, Download, Play, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FloatingHeader } from "@/components/layout/FloatingHeader";
import { FileDropZone } from "@/components/upload/FileDropZone";
import { MetricWidget } from "@/components/metrics/MetricWidget";
import { AnalysisProgress } from "@/components/analysis/AnalysisProgress";
import { ResultsTable } from "@/components/results/ResultsTable";
import { SettingsDrawer } from "@/components/settings/SettingsDrawer";
import { HelpDialog } from "@/components/help/HelpDialog";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

// Mock data for demo
const mockResults = [
  {
    id: "1",
    cluster: "CLU-001",
    tekst: "Dekking voor waterschade door lekkende leidingen of riolering is inbegrepen in de basisverzekering.",
    frequentie: 145,
    advies: "VERWIJDEREN" as const,
    confidence: "Hoog" as const,
    matchScore: 98,
  },
  {
    id: "2",
    cluster: "CLU-002",
    tekst: "9NX3 Aanvullende dekking brand | 9NY3 Stormschade uitbreiding meeverzekerd volgens artikel 12.3",
    frequentie: 67,
    advies: "SPLITSEN" as const,
    confidence: "Hoog" as const,
    matchScore: 95,
  },
  {
    id: "3",
    cluster: "CLU-003",
    tekst: "Standaard clausule voor inboedelverzekering type A met uitgebreide dekking volgens polisvoorwaarden 2024.",
    frequentie: 234,
    advies: "STANDAARDISEREN" as const,
    confidence: "Midden" as const,
    matchScore: 87,
  },
  {
    id: "4",
    cluster: "CLU-004",
    tekst: "Molest meeverzekerd tot maximaal €50.000 per gebeurtenis, afwijkend van standaard polisvoorwaarden.",
    frequentie: 12,
    advies: "BEHOUDEN" as const,
    confidence: "Hoog" as const,
    matchScore: 92,
  },
  {
    id: "5",
    cluster: "CLU-005",
    tekst: "Bijzondere bepalingen conform afspraak met klant dd. 15-03-2023 inzake eigen risico.",
    frequentie: 8,
    advies: "HANDMATIG" as const,
    confidence: "Laag" as const,
    matchScore: 45,
  },
];

const Index = () => {
  const { toast } = useToast();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  
  const [policyFile, setPolicyFile] = useState<{ name: string; size: number } | null>(null);
  const [conditionsFile, setConditionsFile] = useState<{ name: string; size: number } | null>(null);
  
  const [settings, setSettings] = useState({
    clusterAccuracy: 90,
    minFrequency: 20,
    windowSize: 200,
    aiEnabled: true,
  });

  const [progressSteps, setProgressSteps] = useState<
    { id: string; label: string; status: "pending" | "active" | "completed" }[]
  >([
    { id: "1", label: "Ingestie", status: "pending" },
    { id: "2", label: "Clustering", status: "pending" },
    { id: "3", label: "Sanering", status: "pending" },
    { id: "4", label: "Compliance", status: "pending" },
  ]);

  const handlePolicyUpload = useCallback((files: File[]) => {
    const file = files[0];
    setPolicyFile({ name: file.name, size: file.size });
    toast({
      title: "Bestand geüpload",
      description: `${file.name} is succesvol toegevoegd.`,
    });
  }, [toast]);

  const handleConditionsUpload = useCallback((files: File[]) => {
    const file = files[0];
    setConditionsFile({ name: file.name, size: file.size });
    toast({
      title: "Voorwaarden geüpload",
      description: `${file.name} is succesvol toegevoegd.`,
    });
  }, [toast]);

  const simulateAnalysis = useCallback(async () => {
    setIsAnalyzing(true);
    setAnalysisComplete(false);
    
    const steps = ["1", "2", "3", "4"];
    
    for (let i = 0; i < steps.length; i++) {
      setProgressSteps((prev) =>
        prev.map((step, idx) => ({
          ...step,
          status: idx === i ? "active" : idx < i ? "completed" : "pending",
        }))
      );
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    
    setProgressSteps((prev) =>
      prev.map((step) => ({ ...step, status: "completed" }))
    );
    
    setIsAnalyzing(false);
    setAnalysisComplete(true);
    
    toast({
      title: "Analyse voltooid",
      description: "Uw resultaten zijn klaar om te bekijken.",
    });
  }, [toast]);

  const handleStartAnalysis = useCallback(() => {
    if (!policyFile || !conditionsFile) {
      toast({
        title: "Bestanden ontbreken",
        description: "Upload eerst zowel het polisbestand als de voorwaarden.",
        variant: "destructive",
      });
      return;
    }
    simulateAnalysis();
  }, [policyFile, conditionsFile, simulateAnalysis, toast]);

  const handleDownload = useCallback(() => {
    toast({
      title: "Download gestart",
      description: "Uw Excel rapport wordt voorbereid...",
    });
  }, [toast]);

  const canStartAnalysis = policyFile && conditionsFile && !isAnalyzing;

  return (
    <div className="min-h-screen bg-background">
      <FloatingHeader
        onSettingsClick={() => setSettingsOpen(true)}
        onHelpClick={() => setHelpOpen(true)}
      />

      <main className="container max-w-7xl mx-auto px-4 pb-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column - Input */}
          <div className="lg:col-span-4 space-y-6">
            <FileDropZone
              title="Polisbestand"
              description="Sleep uw Excel/CSV bestand hier"
              accept=".xlsx,.xls,.csv"
              onFileSelect={handlePolicyUpload}
              status={policyFile ? "success" : "idle"}
              uploadedFile={policyFile}
              className="animate-fade-up"
            />

            <FileDropZone
              title="Voorwaarden & Clausules"
              description="Sleep voorwaarden PDF/TXT hier"
              accept=".pdf,.txt,.docx"
              onFileSelect={handleConditionsUpload}
              status={conditionsFile ? "success" : "idle"}
              uploadedFile={conditionsFile}
              className="animate-fade-up animation-delay-100"
            />

            <Button
              onClick={handleStartAnalysis}
              disabled={!canStartAnalysis}
              className={cn(
                "btn-primary-cta w-full h-14 text-sm rounded-xl",
                "animate-fade-up animation-delay-200"
              )}
            >
              {isAnalyzing ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <Play className="w-5 h-5 mr-2" />
                  Start Analyse
                </>
              )}
            </Button>
          </div>

          {/* Right Column - Output */}
          <div className="lg:col-span-8 space-y-6">
            {/* Metrics Row */}
            {analysisComplete && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-up">
                <MetricWidget
                  icon={FileStack}
                  label="Verwerkte Rijen"
                  value="1,247"
                  subValue="van 1,247 totaal"
                  variant="default"
                />
                <MetricWidget
                  icon={TrendingDown}
                  label="Reductie"
                  value="68%"
                  subValue="853 rijen minder"
                  variant="success"
                />
                <MetricWidget
                  icon={Network}
                  label="Clusters"
                  value="127"
                  subValue="unieke groepen"
                  variant="primary"
                />
              </div>
            )}

            {/* Progress */}
            {isAnalyzing && (
              <AnalysisProgress steps={progressSteps} className="animate-fade-up" />
            )}

            {/* Results */}
            {analysisComplete && (
              <div className="space-y-4 animate-fade-up animation-delay-200">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-foreground">
                    Analyse Resultaten
                  </h2>
                  <Button
                    onClick={handleDownload}
                    variant="outline"
                    className="btn-download"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download Rapport
                  </Button>
                </div>
                <ResultsTable data={mockResults} />
              </div>
            )}

            {/* Empty State */}
            {!isAnalyzing && !analysisComplete && (
              <div className="floating-card flex flex-col items-center justify-center py-20 text-center animate-fade-up animation-delay-300">
                <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mb-6">
                  <FileStack className="w-10 h-10 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  Klaar om te starten
                </h3>
                <p className="text-muted-foreground max-w-md">
                  Upload uw polisbestand en voorwaarden om de analyse te starten.
                  De resultaten verschijnen hier.
                </p>
              </div>
            )}
          </div>
        </div>
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

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
};

export default Index;
