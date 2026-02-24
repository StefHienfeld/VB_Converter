import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchLibraries, type LibraryInfo } from "@/lib/api";
import { cn } from "@/lib/utils";
import { BookOpen, ChevronDown, X } from "lucide-react";

interface LibrarySelectorProps {
  selectedLibraryId: string | null;
  onSelect: (library: LibraryInfo | null) => void;
  className?: string;
}

export function LibrarySelector({ selectedLibraryId, onSelect, className }: LibrarySelectorProps) {
  const [open, setOpen] = useState(false);

  const { data: libraries = [], isLoading } = useQuery({
    queryKey: ["libraries", "active"],
    queryFn: () => fetchLibraries("active"),
    staleTime: 30_000,
  });

  const selected = libraries.find((l) => l.id === selectedLibraryId);

  if (isLoading) return null;
  if (libraries.length === 0) return null;

  return (
    <div className={cn("floating-card p-4 relative z-20", className)}>
      <div className="flex items-center gap-3">
        <BookOpen className="w-5 h-5 text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground mb-1">Product Bibliotheek</p>
          <div className="relative">
            <button
              onClick={() => setOpen(!open)}
              className={cn(
                "w-full flex items-center justify-between gap-2 px-3 py-2 rounded-xl",
                "border border-border/50 bg-background text-sm",
                "hover:border-primary/30 transition-colors",
                selected && "border-primary/30 bg-primary/5"
              )}
            >
              <span className={cn("truncate", !selected && "text-muted-foreground")}>
                {selected
                  ? selected.naam + (selected.versie ? " (" + selected.versie + ")" : "") + " — " + selected.section_count + " secties"
                  : "Geen bibliotheek (handmatig uploaden)"}
              </span>
              <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />
            </button>

            {open && (
              <div className="absolute z-50 w-full mt-1 py-1 rounded-xl border border-border/50 bg-card shadow-floating">
                <button
                  onClick={() => { onSelect(null); setOpen(false); }}
                  className={cn(
                    "w-full px-3 py-2 text-left text-sm hover:bg-muted/50 transition-colors",
                    !selected && "bg-primary/5 text-primary font-medium"
                  )}
                >
                  Geen bibliotheek (handmatig uploaden)
                </button>
                {libraries.map((lib) => (
                  <button
                    key={lib.id}
                    onClick={() => { onSelect(lib); setOpen(false); }}
                    className={cn(
                      "w-full px-3 py-2 text-left text-sm hover:bg-muted/50 transition-colors",
                      lib.id === selectedLibraryId && "bg-primary/5 text-primary font-medium"
                    )}
                  >
                    <span className="font-medium">{lib.naam}</span>
                    {lib.verzekeraar && <span className="text-muted-foreground"> — {lib.verzekeraar}</span>}
                    {lib.versie && <span className="text-muted-foreground"> ({lib.versie})</span>}
                    <span className="text-muted-foreground ml-2">{lib.section_count} secties</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        {selected && (
          <button
            onClick={() => onSelect(null)}
            className="p-1 rounded-full hover:bg-muted/50 text-muted-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}