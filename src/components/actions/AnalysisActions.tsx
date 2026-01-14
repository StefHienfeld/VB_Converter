/**
 * Component for analysis action buttons (Start, Cancel, Download).
 */

import { Play, Loader2, Download, Sparkles, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
  aiEnabled: boolean;
  onAiToggle: (enabled: boolean) => void;
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
  aiEnabled,
  onAiToggle,
  className,
}: AnalysisActionsProps) {
  return (
    <div className={cn("flex flex-col items-center gap-4 relative z-10", className)}>
      {/* AI Toggle - prominent placement */}
      {inputView !== "compact" && (
        <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-card/50 border border-border/50 animate-fade-up animation-delay-200">
          <Sparkles className={cn(
            "w-4 h-4 transition-colors",
            aiEnabled ? "text-amber-500" : "text-muted-foreground"
          )} />
          <Label 
            htmlFor="ai-toggle" 
            className="text-sm font-medium cursor-pointer select-none"
          >
            AI Analyse (OpenAI)
          </Label>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="w-3.5 h-3.5 text-muted-foreground hover:text-foreground cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-xs">
                <strong>AI Analyse</strong> gebruikt OpenAI GPT voor slimmere clausule-matching, redundantie-checks en compliance analyse.
              </p>
            </TooltipContent>
          </Tooltip>
          <Switch
            id="ai-toggle"
            checked={aiEnabled}
            onCheckedChange={onAiToggle}
          />
          {aiEnabled && (
            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
              Actief
            </span>
          )}
        </div>
      )}

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
              {aiEnabled && <Sparkles className="w-4 h-4 ml-2 text-amber-400" />}
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
