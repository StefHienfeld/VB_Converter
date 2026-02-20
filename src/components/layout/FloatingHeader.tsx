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
    <header className="container max-w-7xl mx-auto mt-6 mb-8 px-4 animate-slide-down relative z-20">
      <div className="relative flex items-center justify-between h-20 floating-card px-6">
        {/* Left: Logo */}
        <div className="flex items-center gap-3 z-10">
          <img
            src={hienfeldLogo}
            alt="Hienfeld Logo"
            className="h-11 w-auto"
          />
        </div>

        {/* Center: Title */}
        <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <h1 className="text-xl font-bold tracking-tight whitespace-nowrap">
            <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
              VB Converter
            </span>
          </h1>
        </div>

        {/* Right: Actions */}
        <nav className="flex items-center gap-1 z-10" aria-label="Acties">
          <Button
            variant="ghost"
            size="icon"
            onClick={onHelpClick}
            className="rounded-full hover:bg-secondary/20 transition-colors"
            aria-label="Help openen"
          >
            <HelpCircle className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onSettingsClick}
            className={cn(
              "rounded-full hover:bg-secondary/20 transition-all",
              "hover:rotate-90 duration-300"
            )}
            aria-label="Instellingen openen"
          >
            <Settings className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
          </Button>
        </nav>
      </div>
    </header>
  );
};
