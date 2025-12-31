/**
 * Component for analysis action buttons (Start, Cancel, Download).
 */

import { Play, Loader2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { InputView } from "@/hooks/useAnalysis";

export interface AnalysisActionsProps {
  inputView: InputView;
  isAnalyzing: boolean;
  analysisComplete: boolean;
  canStartAnalysis: boolean;
  jobId: string | null;
  onStartAnalysis: () => void;
  onCancelAnalysis: () => void;
  onNewAnalysis: () => void;
  onDownload: () => void;
  className?: string;
}

export function AnalysisActions({
  inputView,
  isAnalyzing,
  analysisComplete,
  canStartAnalysis,
  jobId,
  onStartAnalysis,
  onCancelAnalysis,
  onNewAnalysis,
  onDownload,
  className,
}: AnalysisActionsProps) {
  return (
    <div className={cn("flex flex-col items-center gap-4 relative z-10", className)}>
      <div className="flex flex-row items-center gap-3">
        <Button
          onClick={inputView === "compact" ? onNewAnalysis : onStartAnalysis}
          disabled={!canStartAnalysis && inputView !== "compact"}
          className={cn(
            "btn-primary-cta w-full md:w-auto md:min-w-[200px] h-14 text-sm rounded-xl",
            "animate-fade-up animation-delay-300"
          )}
        >
          {isAnalyzing ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : inputView === "compact" ? (
            "Nieuwe Analyse"
          ) : (
            <>
              <Play className="w-5 h-5 mr-2" />
              Start Analyse
            </>
          )}
        </Button>

        {isAnalyzing && (
          <Button
            onClick={onCancelAnalysis}
            variant="outline"
            className={cn(
              "w-full md:w-auto md:min-w-[120px] h-14 text-sm rounded-xl border-destructive/30 text-destructive hover:bg-destructive/10",
              "animate-fade-up animation-delay-300"
            )}
          >
            Annuleer
          </Button>
        )}
      </div>

      {analysisComplete && jobId && (
        <Button
          onClick={onDownload}
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
  );
}
