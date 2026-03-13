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
  created_at: string;
  updated_at: string;
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
