import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

interface SettingsDrawerProps {
  open: boolean;
  onClose: () => void;
  settings: {
    clusterAccuracy: number;
    minFrequency: number;
    windowSize: number;
    aiEnabled: boolean;
  };
  onSettingsChange: (settings: Partial<SettingsDrawerProps["settings"]>) => void;
}

export const SettingsDrawer = ({
  open,
  onClose,
  settings,
  onSettingsChange,
}: SettingsDrawerProps) => {
  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className="glass-panel w-[400px] border-l-0 p-0">
        <SheetHeader className="p-6 pb-0">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-lg font-semibold text-foreground">
              Instellingen
            </SheetTitle>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="rounded-full hover:bg-muted"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </SheetHeader>

        <div className="p-6 space-y-8">
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
          <div className="flex items-center justify-between py-4 border-t border-border">
            <div>
              <Label className="text-sm font-medium text-foreground">
                AI Analyse
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                Gebruik AI voor slimmere matching
              </p>
            </div>
            <Switch
              checked={settings.aiEnabled}
              onCheckedChange={(checked) => onSettingsChange({ aiEnabled: checked })}
            />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};
