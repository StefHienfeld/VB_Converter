import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ProgressStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed";
}

interface AnalysisProgressProps {
  steps: ProgressStep[];
  className?: string;
  children?: React.ReactNode;
  currentProgress?: number; // NEW: Progress percentage (0-100)
  currentMessage?: string;  // NEW: Current backend message
}

export const AnalysisProgress = ({
  steps,
  className,
  children,
  currentProgress,
  currentMessage
}: AnalysisProgressProps) => {
  return (
    <div className={cn("floating-card p-6", className)}>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-base font-semibold text-foreground">Voortgang</h3>
        {currentProgress !== undefined && (
          <span className="text-sm font-semibold text-primary">
            {currentProgress}%
          </span>
        )}
      </div>

      {/* Progress Bar */}
      {currentProgress !== undefined && (
        <div className="mb-6">
          <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-secondary transition-all duration-500 ease-out"
              style={{ width: `${currentProgress}%` }}
            />
          </div>
          {currentMessage && (
            <p className="text-xs text-muted-foreground mt-2 italic">
              {currentMessage}
            </p>
          )}
        </div>
      )}
      
      <div className="space-y-4">
        {steps.map((step, index) => (
          <div key={step.id} className="timeline-step">
            {/* Connector Line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  "absolute left-4 top-8 w-0.5 h-8 -translate-x-1/2",
                  step.status === "completed"
                    ? "bg-primary"
                    : step.status === "active"
                    ? "bg-gradient-to-b from-secondary to-muted"
                    : "bg-muted"
                )}
              />
            )}
            
            {/* Step Dot */}
            <div
              className={cn(
                "timeline-dot",
                step.status === "completed" && "timeline-dot-completed",
                step.status === "active" && "timeline-dot-active",
                step.status === "pending" && "timeline-dot-pending"
              )}
            >
              {step.status === "completed" ? (
                <Check className="w-4 h-4" />
              ) : step.status === "active" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <span className="w-2 h-2 rounded-full bg-current opacity-50" />
              )}
            </div>

            {/* Step Label */}
            <span
              className={cn(
                "text-sm font-medium transition-colors",
                step.status === "completed" && "text-primary",
                step.status === "active" && "text-secondary",
                step.status === "pending" && "text-muted-foreground"
              )}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {children && <div className="mt-6 pt-2">{children}</div>}
    </div>
  );
};
