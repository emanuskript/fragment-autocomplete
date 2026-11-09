import { EvidenceWorkbench } from "../components/evidence-workbench";
import { loadEvidence } from "../lib/evidence";

export const dynamic = "force-dynamic";

export default function Home() {
  return <EvidenceWorkbench evidence={loadEvidence()} />;
}
