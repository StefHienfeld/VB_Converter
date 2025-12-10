import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AnalysisResultRow } from "@/types/analysis";

interface ResultsTableProps {
  data: AnalysisResultRow[];
  className?: string;
}

const adviesBadgeVariant: Record<string, string> = {
  VERWIJDEREN: "badge-verwijderen",
  SPLITSEN: "badge-splitsen",
  STANDAARDISEREN: "badge-standaardiseren",
  BEHOUDEN: "badge-behouden",
  HANDMATIG: "badge-handmatig",
};

const adviesLabels: Record<string, string> = {
  VERWIJDEREN: "Verwijderen",
  SPLITSEN: "Splitsen",
  STANDAARDISEREN: "Standaardiseren",
  BEHOUDEN: "Behouden",
  HANDMATIG: "Handmatig",
};

function normalizeAdvice(code: string): string {
  // Strip any emojis/prefixes coming from backend like "⚠️ GESPLITST"
  const clean = code.replace(/[^\wÀ-ÿ]/g, "").toUpperCase();
  if (clean.includes("VERWIJDER")) return "VERWIJDEREN";
  if (clean.includes("SPLITS")) return "SPLITSEN";
  if (clean.includes("STANDAARD")) return "STANDAARDISEREN";
  if (clean.includes("BEHOUD")) return "BEHOUDEN";
  if (clean.includes("HANDMATIG")) return "HANDMATIG";
  return code;
}

export const ResultsTable = ({ data, className }: ResultsTableProps) => {
  return (
    <div className={cn("floating-card overflow-hidden", className)}>
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full">
          <thead>
            <tr className="bg-muted/50">
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Cluster
              </th>
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Representatieve Tekst
              </th>
              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Freq
              </th>
              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Advies
              </th>
              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Vertrouwen
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {data.map((row) => {
              const adviceCode = normalizeAdvice(row.advice_code);
              const badgeClass = adviesBadgeVariant[adviceCode] ?? "badge-handmatig";
              const label = adviesLabels[adviceCode] ?? row.advice_code;

              return (
                <tr key={row.cluster_id} className="table-row-hover">
                  <td className="px-6 py-4">
                    <span className="text-sm font-medium text-foreground">
                      {row.cluster_name || row.cluster_id}
                    </span>
                  </td>
                  <td className="px-6 py-4 max-w-md">
                    <p className="text-sm text-foreground line-clamp-2">
                      {row.original_text}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className="text-sm font-semibold text-foreground">
                      {row.frequency}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <Badge
                      variant="secondary"
                      className={cn(
                        "px-3 py-1 text-xs font-medium rounded-full",
                        badgeClass
                      )}
                    >
                      {label}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span
                      className={cn(
                        "text-sm font-medium",
                        row.confidence === "Hoog" && "text-success",
                        row.confidence === "Midden" && "text-warning",
                        row.confidence === "Laag" && "text-muted-foreground"
                      )}
                    >
                      {row.confidence}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
