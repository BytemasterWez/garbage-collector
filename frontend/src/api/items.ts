import type {
  CreateItemPayload,
  CreatePdfItemPayload,
  SemanticSearchPayload,
  SemanticSearchResult,
  CreateUrlItemPayload,
  ItemDetail,
  ItemSummary
} from "../types/items";

const API_BASE_URL = "/api";

const BACKEND_UNAVAILABLE_MESSAGE =
  "Backend is unavailable. Confirm the FastAPI server is running on http://127.0.0.1:8000.";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await extractErrorMessage(response);
    throw new Error(message);
  }

  return (await response.json()) as T;
}

async function extractErrorMessage(response: Response): Promise<string> {
  if (response.status >= 500) {
    return BACKEND_UNAVAILABLE_MESSAGE;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { detail?: string };
    if (payload.detail) {
      return payload.detail;
    }
  }

  const text = await response.text();
  return text || "Request failed.";
}

async function makeRequest(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new Error(BACKEND_UNAVAILABLE_MESSAGE);
  }
}

export async function fetchItems(query: string): Promise<ItemSummary[]> {
  const url = new URL(`${API_BASE_URL}/items`, window.location.origin);

  if (query.trim()) {
    url.searchParams.set("q", query.trim());
  }

  const response = await makeRequest(url);
  return handleResponse<ItemSummary[]>(response);
}

export async function fetchItem(itemId: number): Promise<ItemDetail> {
  const response = await makeRequest(`${API_BASE_URL}/items/${itemId}`);
  return handleResponse<ItemDetail>(response);
}

export async function createItem(payload: CreateItemPayload): Promise<ItemDetail> {
  const response = await makeRequest(`${API_BASE_URL}/items`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  return handleResponse<ItemDetail>(response);
}

export async function createUrlItem(payload: CreateUrlItemPayload): Promise<ItemDetail> {
  const response = await makeRequest(`${API_BASE_URL}/items/from-url`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  return handleResponse<ItemDetail>(response);
}

export async function createPdfItem(payload: CreatePdfItemPayload): Promise<ItemDetail> {
  const formData = new FormData();
  formData.append("file", payload.file);

  const response = await makeRequest(`${API_BASE_URL}/items/from-pdf`, {
    method: "POST",
    body: formData
  });

  return handleResponse<ItemDetail>(response);
}

export async function searchSemantic(
  payload: SemanticSearchPayload
): Promise<SemanticSearchResult[]> {
  const response = await makeRequest(`${API_BASE_URL}/retrieval/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      query: payload.query,
      limit: payload.limit ?? 8
    })
  });

  return handleResponse<SemanticSearchResult[]>(response);
}
