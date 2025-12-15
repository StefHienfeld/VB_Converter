import { Zap, Scale, Target } from "lucide-react";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AnalysisMode = "fast" | "balanced" | "accurate";

interface ModeInfo {
  value: AnalysisMode;
  label: string;
  icon: typeof Zap;
  description: string;
  timeMultiplier: number;
  recommended?: boolean;
}

const MODES: ModeInfo[] = [
  {
    value: "fast",
    label: "Fast",
    icon: Zap,
    description: "Snelle analyse met basis tekstmatching (RapidFuzz + Lemma)",
    timeMultiplier: 0.05, // ~20x faster than balanced - ~2s for 1660 rows
  },
  {
    value: "balanced",
    label: "Balanced",
    icon: Scale,
    description: "Optimale balans tussen snelheid en nauwkeurigheid",
    timeMultiplier: 1.0, // Baseline - ~30 seconds for 1660 rows
    recommended: true,
  },
  {
    value: "accurate",
    label: "Accurate",
    icon: Target,
    description: "Beste Nederlandse modellen voor maximale nauwkeurigheid",
    timeMultiplier: 2.5, // ~2.5x slower than balanced - ~75 seconds for 1660 rows
  },
];

interface ModeSelectorProps {
  value: AnalysisMode;
  onChange: (mode: AnalysisMode) => void;
  estimatedRows?: number;
  className?: string;
}

export function ModeSelector({ value, onChange, estimatedRows, className }: ModeSelectorProps) {
  const formatEstimatedTime = (mode: ModeInfo): string => {
    if (!estimatedRows || estimatedRows === 0) {
      return "";
    }

    // Base time calibrated from empirical data (updated for optimized models):
    // 1660 rows: Fast=~2s, Balanced=~30s, Accurate=~75s
    // Balanced base: 30s / 1660 rows = 0.018s per row
    const baseTimePerRow = 0.018;
    const totalSeconds = estimatedRows * baseTimePerRow * mode.timeMultiplier;

    if (totalSeconds < 60) {
      return `~${Math.ceil(totalSeconds)}s`;
    } else if (totalSeconds < 3600) {
      const minutes = Math.ceil(totalSeconds / 60);
      return `~${minutes} min`;
    } else {
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.ceil((totalSeconds % 3600) / 60);
      return `~${hours}u ${minutes}m`;
    }
  };

  return (
    <div className={cn("space-y-3", className)}>
      <div className="space-y-1">
        <Label className="text-base font-semibold">Analyse Modus</Label>
        <p className="text-sm text-muted-foreground">
          Kies tussen snelheid en nauwkeurigheid voor de analyse
        </p>
      </div>

      <RadioGroup
        value={value}
        onValueChange={(val) => onChange(val as AnalysisMode)}
        className="space-y-3"
      >
        {MODES.map((mode) => {
          const Icon = mode.icon;
          const estimatedTime = formatEstimatedTime(mode);
          const isSelected = value === mode.value;

          return (
            <div
              key={mode.value}
              className={cn(
                "flex items-start space-x-3 rounded-lg border-2 p-4 transition-all cursor-pointer hover:border-primary/50",
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card"
              )}
              onClick={() => onChange(mode.value)}
            >
              <RadioGroupItem
                value={mode.value}
                id={mode.value}
                className="mt-1"
              />
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <Icon className={cn(
                    "h-4 w-4",
                    isSelected ? "text-primary" : "text-muted-foreground"
                  )} />
                  <Label
                    htmlFor={mode.value}
                    className={cn(
                      "font-semibold cursor-pointer",
                      isSelected && "text-primary"
                    )}
                  >
                    {mode.label}
                  </Label>
                  {mode.recommended && (
                    <Badge variant="secondary" className="text-xs">
                      Aanbevolen
                    </Badge>
                  )}
                  {estimatedTime && (
                    <span className="text-xs text-muted-foreground ml-auto">
                      {estimatedTime}
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {mode.description}
                </p>
              </div>
            </div>
          );
        })}
      </RadioGroup>
    </div>
  );
}
