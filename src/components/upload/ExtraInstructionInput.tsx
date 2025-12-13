import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ExtraInstructionInputProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

const PLACEHOLDER_TEXT = `meeverzekerde ondernemingen
→ Vullen in partijenkaart

sanctieclausule of embargo
→ Verwijderen - mag weg`;

const HELP_TEXT = `Geef extra instructies mee die de tool moet toepassen.

Format:
  zoektekst (wat je zoekt)
  → actie (wat ermee moet gebeuren)

De tool vergelijkt je zoektekst semantisch met de vrije teksten. Bij een match wordt jouw actie als advies gegeven.

Tip: Schrijf de zoektekst zoals je het in de polis zou verwachten.`;

export const ExtraInstructionInput = ({
  value,
  onChange,
  className,
}: ExtraInstructionInputProps) => {
  return (
    <div className={cn("floating-card p-6", className)}>
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-base font-semibold text-foreground">
          Extra instructies
        </h3>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="h-4 w-4 text-muted-foreground cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="right" className="max-w-sm whitespace-pre-line">
              {HELP_TEXT}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <Textarea
        placeholder={PLACEHOLDER_TEXT}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[120px] resize-none border-muted bg-muted/30 focus:bg-background transition-colors font-mono text-sm"
      />
      <p className="text-xs text-muted-foreground mt-2">
        Laat leeg om geen extra instructies te gebruiken
      </p>
    </div>
  );
};
