import fs from "node:fs";
import path from "node:path";
import dotenv from "dotenv";
import { NextResponse } from "next/server";
import { Client } from "pg";
import { PROJECT_ROOT } from "../../../../lib/evidence";

export const dynamic = "force-dynamic";

function loadDatabaseEnvironment() {
  const envPath = path.join(PROJECT_ROOT, ".env");
  if (!fs.existsSync(envPath)) return;
  const values = dotenv.parse(fs.readFileSync(envPath));
  for (const [key, value] of Object.entries(values)) {
    if (!process.env[key]) process.env[key] = value;
  }
}

export async function GET(_request: Request, context: { params: Promise<{ runId: string }> }) {
  loadDatabaseEnvironment();
  const { runId } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(runId)) {
    return NextResponse.json({ live: false, error: "Invalid segmentation run identifier." }, { status: 400 });
  }
  if (!process.env.FRAGMENT_DB_PASSWORD) {
    return NextResponse.json({ live: false, error: "Local database credentials are not configured." });
  }

  const client = new Client({
    host: process.env.FRAGMENT_DB_HOST ?? "127.0.0.1",
    port: Number(process.env.FRAGMENT_DB_PORT ?? 55432),
    database: process.env.FRAGMENT_DB_NAME ?? "fragment",
    user: process.env.FRAGMENT_DB_USER ?? "fragment",
    password: process.env.FRAGMENT_DB_PASSWORD,
    connectionTimeoutMillis: 1500,
  });
  try {
    await client.connect();
    const run = await client.query(
      `SELECT id::text, image_asset_id::text, fragment_id::text, model_name,
              model_source, status, parameters, confidence_summary,
              created_at, completed_at
         FROM segmentation_run
        WHERE id = $1::uuid`,
      [runId],
    );
    const regions = await client.query(
      `SELECT id::text, label, label_id, confidence,
              ST_AsGeoJSON(bbox_geom)::jsonb AS bbox,
              region_area_px, mask_path, created_at
         FROM layout_region
        WHERE segmentation_run_id = $1::uuid
        ORDER BY confidence DESC NULLS LAST, created_at`,
      [runId],
    );
    return NextResponse.json({
      live: true,
      checkedAt: new Date().toISOString(),
      run: run.rows[0] ?? null,
      regions: regions.rows,
      regionCount: regions.rowCount ?? regions.rows.length,
    });
  } catch (error) {
    return NextResponse.json({
      live: false,
      checkedAt: new Date().toISOString(),
      error: error instanceof Error ? error.message : "Database connection failed.",
    });
  } finally {
    await client.end().catch(() => undefined);
  }
}
