import fs from "node:fs";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { PROJECT_ROOT } from "../../../lib/evidence";

export const dynamic = "force-dynamic";

const ALLOWED_ROOTS = ["data/raw", "outputs", "autocomplete-test-dataset"].map((entry) =>
  path.resolve(PROJECT_ROOT, entry),
);

const MIME_TYPES: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
};

export async function GET(request: NextRequest) {
  const requested = request.nextUrl.searchParams.get("path");
  if (!requested) {
    return NextResponse.json({ error: "Missing artifact path." }, { status: 400 });
  }

  const absolute = path.resolve(PROJECT_ROOT, requested);
  const allowed = ALLOWED_ROOTS.some((root) => absolute === root || absolute.startsWith(`${root}${path.sep}`));
  const mime = MIME_TYPES[path.extname(absolute).toLowerCase()];
  if (!allowed || !mime) {
    return NextResponse.json({ error: "Artifact path is outside the visual evidence allowlist." }, { status: 403 });
  }
  if (!fs.existsSync(absolute)) {
    return NextResponse.json({ error: "Artifact is not present in this local workspace." }, { status: 404 });
  }

  const bytes = await fs.promises.readFile(absolute);
  return new NextResponse(bytes, {
    headers: {
      "Content-Type": mime,
      "Cache-Control": "private, max-age=3600",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
