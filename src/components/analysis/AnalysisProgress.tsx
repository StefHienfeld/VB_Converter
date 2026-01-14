import { Check, Loader2, Clock, AlertCircle, Server } from "lucide-react";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

interface ProgressStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed";
}

interface AnalysisProgressProps {
  steps: ProgressStep[];
  className?: string;
  children?: React.ReactNode;
  currentProgress?: number;
  currentMessage?: string;
  jobStatus?: string;
  startTime?: number; // Timestamp when analysis started
}

// Format elapsed time as "Xm Ys"
function formatElapsedTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

// Get status indicator based on job status
function getStatusIndicator(status: string, progress: number) {
  if (status === "failed") {
    return {
      icon: AlertCircle,
      label: "Mislukt",
      colorClass: "text-destructive",
      bgClass: "bg-destructive/10",
    };
  }
  if (status === "completed" || progress >= 100) {
    return {
      icon: Check,
      label: "Voltooid",
      colorClass: "text-primary",
      bgClass: "bg-primary/10",
    };
  }
  if (status === "pending") {
    return {
      icon: Server,
      label: "Wachten op server",
      colorClass: "text-amber-500",
      bgClass: "bg-amber-500/10",
    };
  }
  return {
    icon: Loader2,
    label: "Bezig",
    colorClass: "text-secondary",
    bgClass: "bg-secondary/10",
  };
}

export const AnalysisProgress = ({
  steps,
  className,
  children,
  currentProgress = 0,
  currentMessage,
  jobStatus = "pending",
  startTime,
}: AnalysisProgressProps) => {
  const [elapsedTime, setElapsedTime] = useState(0);
  
  // Update elapsed time every second
  useEffect(() => {
    if (!startTime || jobStatus === "completed" || jobStatus === "failed") {
      return;
    }
    
    const interval = setInterval(() => {
      setElapsedTime(Date.now() - startTime);
    }, 1000);
    
    return () => clearInterval(interval);
  }, [startTime, jobStatus]);
  
  const statusIndicator = getStatusIndicator(jobStatus, currentProgress);
  const StatusIcon = statusIndicator.icon;
  
  // Determine if we should pulse the progress bar (waiting states)
  const shouldPulse = jobStatus === "pending" || (jobStatus === "running" && currentProgress === 0);
  
  return (
    <div className={cn("floating-card p-6", className)}>
      {/* Header with status badge and timer */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-base font-semibold text-foreground">Voortgang</h3>
          {/* Status badge */}
          <div className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
            statusIndicator.bgClass,
            statusIndicator.colorClass
          )}>
            <StatusIcon className={cn(
              "w-3.5 h-3.5",
              jobStatus === "running" && "animate-spin"
            )} />
            {statusIndicator.label}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Elapsed time */}
          {startTime && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="w-3.5 h-3.5" />
              {formatElapsedTime(elapsedTime)}
            </div>
          )}
          {/* Progress percentage */}
          <span className={cn(
            "text-lg font-bold tabular-nums",
            currentProgress >= 100 ? "text-primary" : "text-foreground"
          )}>
            {currentProgress}%
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className={cn(
          "w-full h-3 bg-muted rounded-full overflow-hidden relative",
          shouldPulse && "animate-pulse"
        )}>
          {/* Background pulsing indicator when waiting */}
          {shouldPulse && (
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-secondary/20 to-transparent animate-shimmer" />
          )}
          {/* Actual progress */}
          <div
            className={cn(
              "h-full transition-all duration-700 ease-out relative",
              currentProgress >= 100 
                ? "bg-primary" 
                : "bg-gradient-to-r from-secondary via-primary to-secondary bg-[length:200%_100%]",
              currentProgress > 0 && currentProgress < 100 && "animate-gradient"
            )}
            style={{ width: `${Math.max(currentProgress, shouldPulse ? 3 : 0)}%` }}
          >
            {/* Shine effect */}
            {currentProgress > 0 && currentProgress < 100 && (
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shine" />
            )}
          </div>
        </div>
        
        {/* Status message */}
        <div className="flex items-center justify-between mt-2">
          <p className={cn(
            "text-sm",
            currentMessage ? "text-foreground" : "text-muted-foreground italic"
          )}>
            {currentMessage || (shouldPulse ? "Even geduld..." : "Klaar om te starten")}
          </p>
        </div>
      </div>
      
      {/* Steps timeline */}
      <div className="space-y-3 mt-6 pt-4 border-t border-border/50">
        {steps.map((step, index) => (
          <div key={step.id} className="timeline-step">
            {/* Connector Line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  "absolute left-4 top-8 w-0.5 h-6 -translate-x-1/2 transition-colors duration-300",
                  step.status === "completed"
                    ? "bg-primary"
                    : step.status === "active"
                    ? "bg-gradient-to-b from-secondary to-muted"
                    : "bg-muted/50"
                )}
              />
            )}
            
            {/* Step Dot */}
            <div
              className={cn(
                "timeline-dot transition-all duration-300",
                step.status === "completed" && "timeline-dot-completed scale-100",
                step.status === "active" && "timeline-dot-active scale-110",
                step.status === "pending" && "timeline-dot-pending scale-90 opacity-60"
              )}
            >
              {step.status === "completed" ? (
                <Check className="w-4 h-4" />
              ) : step.status === "active" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <span className="w-2 h-2 rounded-full bg-current opacity-40" />
              )}
            </div>

            {/* Step Label */}
            <span
              className={cn(
                "text-sm font-medium transition-all duration-300",
                step.status === "completed" && "text-primary",
                step.status === "active" && "text-secondary font-semibold",
                step.status === "pending" && "text-muted-foreground/60"
              )}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {children && <div className="mt-6 pt-4 border-t border-border/50">{children}</div>}
    </div>
  );
};
