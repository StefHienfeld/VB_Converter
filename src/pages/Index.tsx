/**
 * Main page component - slim version using custom hooks and wrapper components.
 */

import { useState } from "react";
import { FileStack, TrendingDown, Network, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FloatingHeader } from "@/components/layout/FloatingHeader";
import { FileUploadSection } from "@/components/upload/FileUploadSection";
import { AnalysisActions } from "@/components/actions/AnalysisActions";
import { MetricWidget } from "@/components/metrics/MetricWidget";
import { AnalysisProgress } from "@/components/analysis/AnalysisProgress";
import { ResultsTable } from "@/components/results/ResultsTable";
import { SettingsDrawer } from "@/components/settings/SettingsDrawer";
import { HelpDialog } from "@/components/help/HelpDialog";
import { useAnalysis } from "@/hooks/useAnalysis";
import { cn } from "@/lib/utils";

const Index = () => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const analysis = useAnalysis();

  return (
    <div className="min-h-screen bg-background">
      <FloatingHeader
        onSettingsClick={() => setSettingsOpen(true)}
        onHelpClick={() => setHelpOpen(true)}
      />

      <main className="container max-w-7xl mx-auto px-4 pb-12">
        {/* Input Section */}
        <div className="transition-all duration-700 ease-in-out">
          <FileUploadSection
            policyFile={analysis.policyFile}
            onPolicyUpload={analysis.handlePolicyUpload}
            conditionsFiles={analysis.conditionsFiles}
            onConditionsUpload={analysis.handleConditionsUpload}
            clauseLibraryFiles={analysis.clauseLibraryFiles}
            onClauseLibraryUpload={analysis.handleClauseLibraryUpload}
            extraInstruction={analysis.extraInstruction}
            onExtraInstructionChange={analysis.setExtraInstruction}
            isCompact={analysis.inputView === "compact"}
          />

          <AnalysisActions
            inputView={analysis.inputView}
            isAnalyzing={analysis.isAnalyzing}
            analysisComplete={analysis.analysisComplete}
            canStartAnalysis={analysis.canStartAnalysis}
            jobId={analysis.jobId}
            onStartAnalysis={analysis.handleStartAnalysis}
            onCancelAnalysis={analysis.handleCancelAnalysis}
            onNewAnalysis={analysis.handleNewAnalysis}
            onDownload={analysis.handleDownload}
            className="mb-8"
          />
        </div>

        {/* Output Section */}
        {(analysis.isAnalyzing || analysis.analysisComplete) && (
          <div className="space-y-6">
            {/* Metrics Row */}
            {analysis.analysisComplete && analysis.stats && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 animate-fade-up">
                <MetricWidget
                  icon={FileStack}
                  label="Verwerkte Rijen"
                  value={analysis.stats.total_rows ?? 0}
                  subValue={
                    analysis.stats.total_rows
                      ? `${analysis.stats.total_rows} rijen geanalyseerd`
                      : undefined
                  }
                  variant="default"
                />
                <MetricWidget
                  icon={TrendingDown}
                  label="Reductie"
                  value={`${analysis.stats.reduction_percentage ?? 0}%`}
                  subValue={
                    analysis.stats.total_rows && analysis.stats.unique_clusters
                      ? `${analysis.stats.total_rows - analysis.stats.unique_clusters} rijen minder`
                      : undefined
                  }
                  variant="success"
                />
                <MetricWidget
                  icon={Network}
                  label="Clusters"
                  value={analysis.stats.unique_clusters ?? 0}
                  subValue="unieke groepen"
                  variant="primary"
                />
              </div>
            )}

            {/* Progress & Results */}
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,280px)_minmax(0,1fr)] gap-4 items-start">
              <AnalysisProgress
                steps={analysis.progressSteps}
                currentProgress={analysis.currentProgress}
                currentMessage={analysis.currentMessage}
                className="order-2 lg:order-1 animate-fade-up animation-delay-200"
              >
                {analysis.analysisComplete && (
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={analysis.handleDownload}
                    disabled={!analysis.analysisComplete || !analysis.jobId}
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
                {analysis.analysisComplete && (
                  <ResultsTable
                    data={analysis.results.slice(0, 10)}
                    className="animate-fade-up animation-delay-200"
                  />
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
        settings={analysis.settings}
        onSettingsChange={(newSettings) =>
          analysis.setSettings((prev) => ({ ...prev, ...newSettings }))
        }
        estimatedRows={analysis.estimatedRows}
      />

      <HelpDialog open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  );
};

export default Index;
