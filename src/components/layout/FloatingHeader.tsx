import { Settings, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import hienfeldLogo from "@/assets/hienfeld-logo.png";

interface FloatingHeaderProps {
  onSettingsClick?: () => void;
  onHelpClick?: () => void;
}

export const FloatingHeader = ({ onSettingsClick, onHelpClick }: FloatingHeaderProps) => {
  return (
    <header className="w-[95%] mx-auto mt-6 mb-8 floating-card px-6 py-4 animate-slide-down">
      <div className="flex items-center justify-between">
        {/* Logo & Title */}
        <div className="flex items-center gap-3">
          <img 
            src={hienfeldLogo} 
            alt="Hienfeld Logo" 
            className="h-10 w-auto"
          />
          <h1 className="text-lg font-bold text-foreground tracking-tight">
            VB Converter
          </h1>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onHelpClick}
            className="rounded-full hover:bg-secondary/20 transition-colors"
          >
            <HelpCircle className="w-5 h-5 text-muted-foreground" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onSettingsClick}
            className={cn(
              "rounded-full hover:bg-secondary/20 transition-all",
              "hover:rotate-90 duration-300"
            )}
          >
            <Settings className="w-5 h-5 text-muted-foreground" />
          </Button>
        </div>
      </div>
    </header>
  );
};
