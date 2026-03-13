export type ItemSummary = {
  id: number;
  item_type: "pasted_text" | "url" | "pdf";
  source_url: string | null;
  source_filename: string | null;
  title: string;
  preview: string;
  created_at: string;
  updated_at: string;
};

export type ItemDetail = {
  id: number;
  item_type: "pasted_text" | "url" | "pdf";
  source_url: string | null;
  source_filename: string | null;
  title: string;
  content: string;
  metadata: ItemMetadata;
  entities: ItemEntities;
  created_at: string;
  updated_at: string;
};

export type RelatedItem = {
  item_id: number;
  item_type: "pasted_text" | "url" | "pdf";
  title: string;
  source_url: string | null;
  source_filename: string | null;
  score: number;
  reason: string;
  matching_chunk_preview: string;
};

export type ItemMetadata = {
  item_type: "pasted_text" | "url" | "pdf" | string;
  word_count: number;
  character_count: number;
  line_count: number;
  hostname: string | null;
  source_filename: string | null;
};

export type ItemEntities = {
  people: string[];
  organizations: string[];
  places: string[];
  dates: string[];
};

export type CreateItemPayload = {
  content: string;
};

export type CreateUrlItemPayload = {
  url: string;
};

export type CreatePdfItemPayload = {
  file: File;
};

export type SemanticSearchPayload = {
  query: string;
  limit?: number;
};

export type SemanticSearchResult = {
  item_id: number;
  item_type: "pasted_text" | "url" | "pdf";
  item_title: string;
  source_url: string | null;
  source_filename: string | null;
  chunk_id: number;
  chunk_index: number;
  chunk_text: string;
  score: number;
};

export type ChatAnswerPayload = {
  question: string;
  retrieval_limit?: number;
};

export type ChatCitation = {
  source_id: string;
  item_id: number;
  item_type: "pasted_text" | "url" | "pdf";
  item_title: string;
  source_url: string | null;
  source_filename: string | null;
  chunk_id: number;
  chunk_index: number;
  chunk_text: string;
  score: number;
};

export type ChatAnswerResponse = {
  answer: string;
  citations: ChatCitation[];
};

export type GoalDefinition = {
  id: string;
  name: string;
  description: string;
};

export type KernelEvidence = {
  evidence_type: string;
  source_id: string;
  source_item_id: string;
  snippet: string;
  relevance: number;
  confidence: number;
  observed_at: string;
  provenance: Record<string, unknown>;
};

export type KernelMatchedTarget = {
  target_id: string;
  label: string;
  strength: number;
};

export type GoalAlignmentResult = {
  contract_version: "kernel.v1";
  engine_name: "goal_alignment";
  subject: {
    subject_type: string;
    subject_id: string;
  };
  summary: string;
  classification: "match" | "weak_match" | "no_match";
  score: number;
  confidence: number;
  rationale: string;
  evidence: KernelEvidence[];
  signals: {
    relevance: number;
    novelty: number;
    actionability: number;
    recurrence: number;
  };
  outputs: {
    matched_targets: KernelMatchedTarget[];
    recommended_action: "review" | "hold" | "ignore";
    tags: string[];
  };
  provenance: {
    generated_at: string;
    source_system: string;
    engine_version: string;
  };
};
