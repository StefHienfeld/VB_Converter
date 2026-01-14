import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ModeSelector, AnalysisMode } from "./ModeSelector";

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
  settings: {
    clusterAccuracy: number;
    minFrequency: number;
    windowSize: number;
    aiEnabled: boolean;
    analysisMode: AnalysisMode;
  };
  onSettingsChange: (settings: Partial<SettingsDrawerProps["settings"]>) => void;
  estimatedRows?: number;
}

export const SettingsDrawer = ({
  open,
  onClose,
  settings,
  onSettingsChange,
  estimatedRows,
}: SettingsDrawerProps) => {
  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className="glass-panel w-[400px] sm:w-[450px] border-l-0 p-0 flex flex-col overflow-x-hidden">
        <SheetHeader className="p-6 pb-0 shrink-0">
          <SheetTitle className="text-lg font-semibold text-foreground">
            Instellingen
          </SheetTitle>
        </SheetHeader>

        <div className="p-6 space-y-8 overflow-y-auto flex-1">
          {/* Analysis Mode Selector */}
          <ModeSelector
            value={settings.analysisMode}
            onChange={(mode) => onSettingsChange({ analysisMode: mode })}
            estimatedRows={estimatedRows}
          />

          <div className="border-t border-border" />
          {/* Cluster Accuracy */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium text-foreground">
                Cluster Nauwkeurigheid
              </Label>
              <span className="text-sm font-semibold text-primary">
                {settings.clusterAccuracy}%
              </span>
            </div>
            <Slider
              value={[settings.clusterAccuracy]}
              onValueChange={([value]) => onSettingsChange({ clusterAccuracy: value })}
              min={80}
              max={100}
              step={1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Hogere waarde = strengere clustering
            </p>
          </div>

          {/* Min Frequency */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium text-foreground">
                Min. Frequentie
              </Label>
              <span className="text-sm font-semibold text-primary">
                {settings.minFrequency}
              </span>
            </div>
            <Slider
              value={[settings.minFrequency]}
              onValueChange={([value]) => onSettingsChange({ minFrequency: value })}
              min={5}
              max={50}
              step={5}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Minimum voorkomens voor standaardisatie
            </p>
          </div>

          {/* Window Size */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium text-foreground">
                Window Size
              </Label>
              <span className="text-sm font-semibold text-primary">
                {settings.windowSize}
              </span>
            </div>
            <Slider
              value={[settings.windowSize]}
              onValueChange={([value]) => onSettingsChange({ windowSize: value })}
              min={50}
              max={500}
              step={50}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Aantal clusters voor vergelijking
            </p>
          </div>

          {/* AI Toggle */}
          <div className="py-4 border-t border-border">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <Label htmlFor="ai-toggle-settings" className="text-sm font-medium text-foreground block">
                  AI Analyse (OpenAI)
                </Label>
                <p className="text-xs text-muted-foreground mt-1">
                  GPT voor slimmere clausule-analyse
                </p>
              </div>
              <div className="flex-shrink-0 flex items-center justify-end" style={{ minWidth: '60px' }}>
                <Switch
                  id="ai-toggle-settings"
                  checked={settings.aiEnabled}
                  onCheckedChange={(checked) => {
                    console.log('AI toggle changed:', checked);
                    onSettingsChange({ aiEnabled: checked });
                  }}
                  className="flex-shrink-0 relative z-10"
                  aria-label="Toggle AI Analyse"
                />
              </div>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};
