import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ResultRow {
  id: string;
  cluster: string;
  tekst: string;
  frequentie: number;
  advies: "VERWIJDEREN" | "SPLITSEN" | "STANDAARDISEREN" | "BEHOUDEN" | "HANDMATIG";
  confidence: "Hoog" | "Midden" | "Laag";
  matchScore?: number;
}

interface ResultsTableProps {
  data: ResultRow[];
  className?: string;
}

const adviesBadgeVariant = {
  VERWIJDEREN: "badge-verwijderen",
  SPLITSEN: "badge-splitsen",
  STANDAARDISEREN: "badge-standaardiseren",
  BEHOUDEN: "badge-behouden",
  HANDMATIG: "badge-handmatig",
};

const adviesLabels = {
  VERWIJDEREN: "Verwijderen",
  SPLITSEN: "Splitsen",
  STANDAARDISEREN: "Standaardiseren",
  BEHOUDEN: "Behouden",
  HANDMATIG: "Handmatig",
};

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
                Match
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {data.map((row) => (
              <tr key={row.id} className="table-row-hover">
                <td className="px-6 py-4">
                  <span className="text-sm font-medium text-foreground">
                    {row.cluster}
                  </span>
                </td>
                <td className="px-6 py-4 max-w-md">
                  <p className="text-sm text-foreground line-clamp-2">
                    {row.tekst}
                  </p>
                </td>
                <td className="px-6 py-4 text-center">
                  <span className="text-sm font-semibold text-foreground">
                    {row.frequentie}
                  </span>
                </td>
                <td className="px-6 py-4 text-center">
                  <Badge
                    variant="secondary"
                    className={cn(
                      "px-3 py-1 text-xs font-medium rounded-full",
                      adviesBadgeVariant[row.advies]
                    )}
                  >
                    {adviesLabels[row.advies]}
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
                    {row.matchScore ? `${row.matchScore}%` : row.confidence}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
