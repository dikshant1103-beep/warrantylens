import type {
  Claim,
  ClaimList,
  ClaimStatusResponse,
  Completeness,
  CompletenessStats,
  DashboardOverview,
  Decision,
  Detection,
  Evidence,
  LoginResponse,
  MediaKind,
  OcrResult,
  Report,
  Review,
  Risk,
  RiskDistribution,
  Transcript,
  UploadSlot,
  User,
  VlmAnalysis,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const ACCESS_KEY = "wl_access";
const REFRESH_KEY = "wl_refresh";

// NOTE (project simplicity): tokens are kept in localStorage. In production the
// refresh token should live in an httpOnly cookie via a BFF; the access token
// stays in memory. The API contract here supports either approach.
export const tokenStore = {
  access: () => (typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY)),
  refresh: () => (typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY)),
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function refreshAccess(): Promise<boolean> {
  const refresh = tokenStore.refresh();
  if (!refresh) return false;
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  tokenStore.set(data.access_token);
  return true;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const access = tokenStore.access();
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401 && retry && (await refreshAccess())) {
    return request<T>(path, options, false);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  async login(email: string, password: string, tenant_slug?: string) {
    const data = await request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, tenant_slug }),
    });
    tokenStore.set(data.access_token, data.refresh_token);
    return data;
  },
  async logout() {
    const refresh = tokenStore.refresh();
    if (refresh) {
      await request("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      }).catch(() => undefined);
    }
    tokenStore.clear();
  },
  me: () => request<User>("/auth/me"),
  listUsers: (page = 1, size = 20) =>
    request<{ items: User[]; total: number; page: number; size: number }>(
      `/users?page=${page}&size=${size}`,
    ),

  // --- Claims ---
  listClaims: (page = 1, size = 20, status?: string) =>
    request<ClaimList>(
      `/claims?page=${page}&size=${size}${status ? `&status=${status}` : ""}`,
    ),
  getClaim: (id: string) => request<Claim>(`/claims/${id}`),
  createClaim: (body: Partial<Claim>) =>
    request<Claim>("/claims", { method: "POST", body: JSON.stringify(body) }),
  submitClaim: (id: string) =>
    request<Claim>(`/claims/${id}/submit`, { method: "POST" }),
  getEvidence: (id: string) => request<Evidence>(`/claims/${id}/evidence`),
  getStatus: (id: string) => request<ClaimStatusResponse>(`/claims/${id}/status`),
  getTranscript: (id: string) => request<Transcript[]>(`/claims/${id}/transcript`),
  getDetections: (id: string) => request<Detection[]>(`/claims/${id}/detections`),
  getOcr: (id: string) => request<OcrResult[]>(`/claims/${id}/ocr`),
  getVlm: (id: string) => request<VlmAnalysis[]>(`/claims/${id}/vlm`),
  getCompleteness: (id: string) => request<Completeness | null>(`/claims/${id}/completeness`),
  getRisk: (id: string) => request<Risk | null>(`/claims/${id}/risk`),
  getReport: (id: string) => request<Report | null>(`/claims/${id}/report`),
  regenerateReport: (id: string) =>
    request<Report>(`/claims/${id}/report/regenerate`, { method: "POST" }),
  getReviews: (id: string) => request<Review[]>(`/claims/${id}/reviews`),
  submitReview: (id: string, decision: Decision, notes?: string) =>
    request<Review>(`/claims/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, notes: notes ?? null }),
    }),

  // --- Dashboard ---
  dashOverview: () => request<DashboardOverview>("/dashboard/overview"),
  dashRisk: () => request<RiskDistribution>("/dashboard/risk-distribution"),
  dashCompleteness: () => request<CompletenessStats>("/dashboard/completeness-stats"),
  dashQueue: () =>
    request<
      {
        id: string;
        claim_number: string;
        vin: string | null;
        risk_score: number | null;
        completeness_score: number | null;
      }[]
    >("/dashboard/reviewer-queue"),

  requestUploads: (
    id: string,
    files: { filename: string; content_type: string; kind: MediaKind; size: number }[],
  ) =>
    request<{ uploads: UploadSlot[] }>(`/claims/${id}/uploads`, {
      method: "POST",
      body: JSON.stringify({ files }),
    }),
  completeUpload: (claimId: string, assetId: string, sha256?: string) =>
    request(`/claims/${claimId}/uploads/${assetId}/complete`, {
      method: "POST",
      body: JSON.stringify({ sha256: sha256 ?? null }),
    }),

  // Direct PUT to the presigned S3 URL (bytes never touch our API).
  async uploadToS3(url: string, file: File) {
    const res = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": file.type },
      body: file,
    });
    if (!res.ok) throw new Error(`Upload failed (${res.status})`);
  },
};

export { ApiError };
