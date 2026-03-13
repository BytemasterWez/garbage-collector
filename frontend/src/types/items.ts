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
