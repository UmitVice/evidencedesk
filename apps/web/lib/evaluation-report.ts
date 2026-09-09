import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import offline from "../../../reports/latest-offline.json";

type Report = {
  mode: string;
  label: string;
  commit_sha: string;
  human_review: string;
  methods: Record<
    string,
    { n: number; recall_at_5: number | null; mrr: number | null }
  >;
  outcomes: Array<{
    case_id: string;
    status: string;
    correct_abstention?: boolean | null;
  }>;
};
export function currentReport(): Report {
  const live = resolve(process.cwd(), "../../reports/latest-live.json");
  return existsSync(live)
    ? (JSON.parse(readFileSync(live, "utf8")) as Report)
    : (offline as Report);
}
