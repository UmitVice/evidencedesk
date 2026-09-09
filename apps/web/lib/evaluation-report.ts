import live from "../../../reports/latest-live.json";
import offline from "../../../reports/latest-offline.json";

export type Report = {
  mode: string;
  label: string;
  timestamp: string;
  commit_sha: string;
  prompt_version: string;
  corpus_hash: string;
  dataset_hash: string;
  human_review: string;
  selected_count: number;
  processed_count: number;
  generation_model: string;
  generation_attempts?: number;
  generation_completions?: number;
  embedding_manifest: {
    model: string;
    dimension: number;
    corpus_version: string;
  };
  methods: Record<
    string,
    { n: number; recall_at_5: number | null; mrr: number | null }
  >;
  latency?: { n: number; p50_ms: number; p95_ms: number | null } | null;
  outcomes: Array<{
    case_id: string;
    status: string;
    error_code?: string;
    correct_abstention?: boolean | null;
    schema_valid?: boolean | null;
    citation_integrity?: boolean | null;
    retrieval_misses?: string[];
  }>;
  limitations: string[];
};
export const liveReport = live as Report;
export const offlineReport = offline as Report;
