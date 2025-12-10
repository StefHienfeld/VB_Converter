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
}

export const AnalysisProgress = ({ steps, className }: AnalysisProgressProps) => {
  return (
    <div className={cn("floating-card p-6", className)}>
      <h3 className="text-base font-semibold text-foreground mb-6">Analyse Voortgang</h3>
      
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
    </div>
  );
};
