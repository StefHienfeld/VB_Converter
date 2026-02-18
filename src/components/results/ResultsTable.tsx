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

interface RowData {
  row: AnalysisResultRow;
  adviceCode: string;
  badgeClass: string;
  label: string;
}

function ActionStatus({ status }: { status?: string }) {
  if (!status) return <span className="text-sm text-muted-foreground">-</span>;
  return (
    <span
      className={cn(
        "text-sm font-medium px-2 py-1 rounded",
        status.includes("Afgerond") &&
          "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
        status.includes("Open") &&
          "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
        status.includes("Nieuw") &&
          "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
      )}
    >
      {status}
    </span>
  );
}

function ConfidenceText({ confidence }: { confidence: string }) {
  return (
    <span
      className={cn(
        "text-sm font-medium",
        confidence === "Hoog" && "text-success",
        confidence === "Midden" && "text-warning",
        confidence === "Laag" && "text-muted-foreground"
      )}
    >
      {confidence}
    </span>
  );
}

/** Mobile card layout — shown on screens < md */
function MobileCard({ row, adviceCode, badgeClass, label }: RowData) {
  return (
    <article
      className="rounded-xl border border-border/50 bg-card p-4 space-y-3"
      aria-label={`Cluster ${row.cluster_name || row.cluster_id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-foreground">
          {row.cluster_name || row.cluster_id}
        </span>
        <Badge
          variant="secondary"
          className={cn("px-2.5 py-0.5 text-xs font-medium rounded-full shrink-0", badgeClass)}
        >
          {label}
        </Badge>
      </div>

      <p className="text-sm text-foreground line-clamp-3">{row.original_text}</p>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span>
          <span className="font-medium">Freq:</span>{" "}
          <span className="text-foreground font-semibold">{row.frequency}</span>
        </span>
        <span>
          <span className="font-medium">Vertrouwen:</span>{" "}
          <ConfidenceText confidence={row.confidence} />
        </span>
        {row.action_status && (
          <span>
            <span className="font-medium">Status:</span>{" "}
            <ActionStatus status={row.action_status} />
          </span>
        )}
      </div>
    </article>
  );
}

export const ResultsTable = ({ data, className }: ResultsTableProps) => {
  const rows: RowData[] = data.map((row) => {
    const adviceCode = normalizeAdvice(row.advice_code);
    return {
      row,
      adviceCode,
      badgeClass: adviesBadgeVariant[adviceCode] ?? "badge-handmatig",
      label: adviesLabels[adviceCode] ?? row.advice_code,
    };
  });

  return (
    <div className={cn("floating-card overflow-hidden", className)}>
      {/* Mobile: card list (hidden on md+) */}
      <div className="md:hidden p-4 space-y-3" role="list" aria-label="Analyseresultaten">
        {rows.map(({ row, adviceCode, badgeClass, label }) => (
          <div key={row.cluster_id} role="listitem">
            <MobileCard
              row={row}
              adviceCode={adviceCode}
              badgeClass={badgeClass}
              label={label}
            />
          </div>
        ))}
      </div>

      {/* Desktop: table (hidden below md) */}
      <div className="hidden md:block overflow-x-auto custom-scrollbar">
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
              <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {rows.map(({ row, adviceCode, badgeClass, label }) => (
              <tr key={row.cluster_id} className="table-row-hover">
                <td className="px-6 py-4">
                  <span className="text-sm font-medium text-foreground">
                    {row.cluster_name || row.cluster_id}
                  </span>
                </td>
                <td className="px-6 py-4 max-w-md">
                  <p className="text-sm text-foreground line-clamp-2">{row.original_text}</p>
                </td>
                <td className="px-6 py-4 text-center">
                  <span className="text-sm font-semibold text-foreground">{row.frequency}</span>
                </td>
                <td className="px-6 py-4 text-center">
                  <Badge
                    variant="secondary"
                    className={cn("px-3 py-1 text-xs font-medium rounded-full", badgeClass)}
                  >
                    {label}
                  </Badge>
                </td>
                <td className="px-6 py-4 text-center">
                  <ConfidenceText confidence={row.confidence} />
                </td>
                <td className="px-6 py-4 text-center">
                  <ActionStatus status={row.action_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
