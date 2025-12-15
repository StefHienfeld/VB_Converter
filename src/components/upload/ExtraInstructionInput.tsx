import { cn } from "@/lib/utils";
import { HelpCircle, Plus, Trash2 } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEffect, useMemo, useRef, useState } from "react";

/**
 * ExtraInstructionInput - Table-based custom instructions editor (v4.2)
 * 
 * Provides a user-friendly table interface for defining custom analysis rules.
 * Each row has two columns:
 * - Tekst: The search text/pattern to look for in clauses
 * - Actie: The action to take when a match is found
 * 
 * The component automatically:
 * - Serializes table data to TSV format (zoektekst<TAB>actie) for backend
 * - Parses both TSV and arrow format (backwards compatible)
 * - Validates and normalizes input (removes tabs/newlines from cells)
 * 
 * Matching in backend:
 * - First: Fast case-insensitive contains check (works in all modes)
 * - Fallback: Semantic/fuzzy matching (in BALANCED/ACCURATE modes)
 * 
 * @see hienfeld/services/custom_instructions_service.py for backend implementation
 */
interface ExtraInstructionInputProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

type InstructionRow = {
  id: string;
  text: string;
  action: string;
};

function makeId(): string {
  return `${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function normalizeCellValue(v: string): string {
  // We serialize to TSV (1 row per line). Prevent tabs/newlines from breaking structure.
  return (v ?? "").replace(/\t/g, " ").replace(/\r?\n/g, " ").trim();
}

function serializeRows(rows: InstructionRow[]): string {
  const lines = rows
    .map((r) => ({
      text: normalizeCellValue(r.text),
      action: normalizeCellValue(r.action),
    }))
    .filter((r) => r.text.length > 0 && r.action.length > 0)
    .map((r) => `${r.text}\t${r.action}`);

  return lines.join("\n");
}

function parseArrowFormat(raw: string): InstructionRow[] {
  // Backwards compatible: parse blocks like:
  // zoektekst
  // → actie
  const blocks = raw
    .split(/\n\s*\n/g)
    .map((b) => b.trim())
    .filter(Boolean);

  const rows: InstructionRow[] = [];

  for (const block of blocks) {
    const lines = block
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    if (lines.length === 0) continue;

    let action: string | null = null;
    const searchLines: string[] = [];

    for (const line of lines) {
      const isAction =
        line.startsWith("→") || line.startsWith("->") || line.startsWith(">");
      if (isAction) {
        action = line.replace(/^(→|->|>)\s*/, "").trim();
      } else {
        searchLines.push(line);
      }
    }

    const text = searchLines.join(" ").trim();
    if (text && action) {
      rows.push({ id: makeId(), text, action });
    }
  }

  return rows;
}

function parseTsvLike(raw: string): InstructionRow[] {
  // Preferred format from the UI serialization:
  // zoektekst<TAB>actie
  const lines = raw
    .split(/\r?\n/g)
    .map((l) => l.trim())
    .filter(Boolean);

  const rows: InstructionRow[] = [];
  for (const line of lines) {
    if (line.includes("\t")) {
      const [left, right] = line.split("\t", 2);
      const text = (left ?? "").trim();
      const action = (right ?? "").trim();
      if (text && action) rows.push({ id: makeId(), text, action });
    }
  }
  return rows;
}

const HELP_TEXT = `Geef extra instructies mee die de tool moet toepassen.

Vul per regel een zoektekst en een actie in:
- Tekst: woord/zin die ergens in de clausule voorkomt
- Actie: wat je ermee wilt doen (komt terug als 📋-advies)

Matching werkt als volgt:
1) Eerst: 'bevat' check (hoofdletter-ongevoelig)
2) Daarna: fuzzy/semantische match (als fallback)

Tip: Schrijf de zoektekst zoals je het in de polis zou verwachten.`;

export const ExtraInstructionInput = ({
  value,
  onChange,
  className,
}: ExtraInstructionInputProps) => {
  const initialRows = useMemo<InstructionRow[]>(() => {
    const v = (value ?? "").trim();
    if (!v) return [{ id: makeId(), text: "", action: "" }];

    const tsvRows = parseTsvLike(v);
    if (tsvRows.length > 0) return tsvRows;

    const arrowRows = parseArrowFormat(v);
    if (arrowRows.length > 0) return arrowRows;

    // If parsing fails, keep a single row with the raw value as "text" so user can salvage it.
    return [{ id: makeId(), text: v, action: "" }];
  }, []); // intentionally only once (we handle external updates via effect below)

  const [rows, setRows] = useState<InstructionRow[]>(initialRows);
  const lastEmittedValueRef = useRef<string>(value ?? "");

  // If parent value changes externally (e.g. reset), re-parse into rows.
  useEffect(() => {
    const v = value ?? "";
    if (v === lastEmittedValueRef.current) return;

    const trimmed = v.trim();
    if (!trimmed) {
      setRows([{ id: makeId(), text: "", action: "" }]);
      return;
    }

    const tsvRows = parseTsvLike(trimmed);
    if (tsvRows.length > 0) {
      setRows(tsvRows);
      return;
    }

    const arrowRows = parseArrowFormat(trimmed);
    if (arrowRows.length > 0) {
      setRows(arrowRows);
      return;
    }

    setRows([{ id: makeId(), text: trimmed, action: "" }]);
  }, [value]);

  const commitRows = (nextRows: InstructionRow[]) => {
    setRows(nextRows);
    const serialized = serializeRows(nextRows);
    lastEmittedValueRef.current = serialized;
    onChange(serialized);
  };

  const updateRow = (id: string, patch: Partial<Pick<InstructionRow, "text" | "action">>) => {
    commitRows(
      rows.map((r) => (r.id === id ? { ...r, ...patch } : r)),
    );
  };

  const addRow = () => commitRows([...rows, { id: makeId(), text: "", action: "" }]);

  const removeRow = (id: string) => {
    const next = rows.filter((r) => r.id !== id);
    commitRows(next.length > 0 ? next : [{ id: makeId(), text: "", action: "" }]);
  };

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

      <div className="rounded-xl border border-muted bg-muted/20 overflow-hidden">
        <div className="grid grid-cols-[1fr_1fr_40px] gap-2 px-3 py-2 border-b border-muted bg-muted/30">
          <div className="text-xs font-semibold text-muted-foreground">Tekst</div>
          <div className="text-xs font-semibold text-muted-foreground">Actie</div>
          <div />
        </div>

        <div className="p-3 space-y-2">
          {rows.map((row) => (
            <div key={row.id} className="grid grid-cols-[1fr_1fr_40px] gap-2 items-center">
              <Input
                value={row.text}
                onChange={(e) => updateRow(row.id, { text: e.target.value })}
                placeholder="bijv. meeverzekerde"
                className="bg-background/60"
              />
              <Input
                value={row.action}
                onChange={(e) => updateRow(row.id, { action: e.target.value })}
                placeholder="bijv. Vullen in partijenkaart"
                className="bg-background/60"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeRow(row.id)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Verwijder rij"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}

          <div className="pt-1 flex items-center justify-between">
            <Button type="button" variant="secondary" size="sm" onClick={addRow}>
              <Plus className="h-4 w-4 mr-2" />
              Rij toevoegen
            </Button>

            <p className="text-xs text-muted-foreground">
              Laat leeg om geen extra instructies te gebruiken
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
