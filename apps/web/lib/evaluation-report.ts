// The live record is the pilot run of the current production generator.
import live from "../../../reports/compare-openai-gpt-6-luna-graph-false.json";
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
  split: string;
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
  quality?: {
    n: number;
    fact_pass_rate?: number;
    status_accuracy?: number;
  };
  dataset_counts?: Record<string, number>;
  outcomes: Array<{
    case_id: string;
    status: string;
    error_code?: string;
    correct_abstention?: boolean | null;
    schema_valid?: boolean | null;
    citation_integrity?: boolean | null;
    retrieval_misses?: string[];
    fact_pass?: boolean;
    missing_facts?: string[];
    forbidden_found?: string[];
  }>;
  limitations: string[];
};
export const liveReport = live as Report;
export const offlineReport = offline as Report;
