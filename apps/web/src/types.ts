export type CriterionItem = {
  code: string;
  parent_code: string | null;
  kind: "item" | "alinea" | "bullet" | string;
  statement: string;
  section_code: string | null;
  section_title: string | null;
  criterion_type: string;
  page_start: number;
  page_end: number;
  mandatory_guess: boolean;
  applies_to: string[];
  edital_id?: string;
  version?: string;
  status?: string;
  confidence?: number;
};

export type QueuePayload = {
  id: string;
  label: string;
  edital_id: string;
  version: string;
  source_path: string;
  scope: string;
  count: number;
  items: CriterionItem[];
};

export type ManifestEntry = {
  id: string;
  label: string;
  file: string;
  pdf?: string;
  count: number;
};

export type ReviewAction = "approve" | "edit" | "reject" | "skip";

export type ReviewEvent = {
  id: string;
  queueId: string;
  code: string;
  action: ReviewAction;
  before: string;
  after: string;
  criterion_type: string;
  section_code: string | null;
  page_start: number;
  note: string;
  reviewedAt: string;
};
