import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface ExtraInstructionInputProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export const ExtraInstructionInput = ({
  value,
  onChange,
  className,
}: ExtraInstructionInputProps) => {
  return (
    <div className={cn("floating-card p-6", className)}>
      <h3 className="text-base font-semibold text-foreground mb-4">
        Extra instructies (optioneel)
      </h3>
      <Textarea
        placeholder="Bijv: 'Let extra op clausules over asbest'..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[80px] resize-none border-muted bg-muted/30 focus:bg-background transition-colors"
      />
    </div>
  );
};
