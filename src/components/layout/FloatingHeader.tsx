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
    <header className="container max-w-7xl mx-auto mt-6 mb-8 px-4 animate-slide-down">
      <div className="relative flex items-center justify-between h-20 bg-card/80 backdrop-blur-md rounded-xl border border-border/50 px-6 shadow-sm">
        {/* Left: Logo */}
        <div className="flex items-center gap-3 z-10">
          <img 
            src={hienfeldLogo} 
            alt="Hienfeld Logo" 
            className="h-12 w-auto"
          />
        </div>

        {/* Center: Title */}
        <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <h1 className="text-xl font-bold text-foreground tracking-tight whitespace-nowrap">
            VB Converter
          </h1>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2 z-10">
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
