export type AdviceCode =
  | "VERWIJDEREN"
  | "SPLITSEN"
  | "STANDAARDISEREN"
  | "BEHOUDEN"
  | "HANDMATIG"
  | string;

export type ConfidenceLevel = "Hoog" | "Midden" | "Laag" | string;

export interface AnalysisResultRow {
  cluster_id: string;
  cluster_name: string;
  frequency: number;
  advice_code: AdviceCode;
  confidence: ConfidenceLevel;
  reason: string;
  reference_article: string;
  original_text: string;
  row_type: "SINGLE" | "PARENT" | "CHILD" | string;
  parent_id?: string;
  action_status?: string;  // "✅ Afgerond", "🔲 Open", "🆕 Nieuw"
}


