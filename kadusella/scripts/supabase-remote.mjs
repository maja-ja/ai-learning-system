/**
 * 遠端 Supabase 讀寫 CLI（在你電腦上執行，連到雲端專案）
 *
 * 需要環境變數（放在 .env.local）：
 *   NEXT_PUBLIC_SUPABASE_URL 或 SUPABASE_URL
 *   SUPABASE_SERVICE_ROLE_KEY  （僅本機／CI，勿提交、勿貼到對話）
 *
 * 用法：
 *   npm run sb:peek -- knowledge 30
 *   npm run sb:peek -- knowledge 10 word,definition,meaning
 *   npm run sb:update -- knowledge id <uuid> '{"definition":"新內容"}'
 *   npm run sb:upsert -- knowledge ./data/rows.json word
 *
 * Service Role 會繞過 RLS；請只在信任的環境執行。
 */

import { createClient } from "@supabase/supabase-js";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!url || !key) {
  console.error(
    "缺少 SUPABASE_URL（或 NEXT_PUBLIC_SUPABASE_URL）或 SUPABASE_SERVICE_ROLE_KEY。\n" +
      "請在 .env.local 設定後再執行。",
  );
  process.exit(1);
}

const supabase = createClient(url, key, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const [, , cmd, ...args] = process.argv;

function printJson(data) {
  console.log(JSON.stringify(data, null, 2));
}

async function peek() {
  const table = args[0];
  const limit = Math.min(Number(args[1] ?? 50) || 50, 500);
  const selectCols = args[2] && !args[2].startsWith("-") ? args[2] : "*";

  if (!table) {
    console.error("用法: peek <table> [limit=50] [欄位逗號分隔，預設 *]");
    process.exit(1);
  }

  const { data, error } = await supabase
    .from(table)
    .select(selectCols)
    .limit(limit);

  if (error) {
    console.error(error.message);
    process.exit(1);
  }
  printJson(data);
}

async function updateByPk() {
  const table = args[0];
  const pkCol = args[1];
  const pkVal = args[2];
  const jsonStr = args.slice(3).join(" ");

  if (!table || !pkCol || pkVal === undefined || !jsonStr) {
    console.error(
      '用法: update <table> <pk欄位> <pk值> \'<JSON 物件>\'',
    );
    process.exit(1);
  }

  let patch;
  try {
    patch = JSON.parse(jsonStr);
  } catch {
    console.error("JSON 解析失敗，請用單引號包住整段 JSON");
    process.exit(1);
  }

  const { data, error } = await supabase
    .from(table)
    .update(patch)
    .eq(pkCol, pkVal)
    .select();

  if (error) {
    console.error(error.message);
    process.exit(1);
  }
  printJson(data);
}

async function upsertFile() {
  const table = args[0];
  const filePath = args[1];
  const onConflict = args[2];

  if (!table || !filePath || !onConflict) {
    console.error("用法: upsert <table> <json檔路徑> <onConflict欄位>");
    console.error("範例: upsert knowledge ./rows.json word");
    process.exit(1);
  }

  const abs = resolve(process.cwd(), filePath);
  if (!existsSync(abs)) {
    console.error("找不到檔案:", abs);
    process.exit(1);
  }

  const raw = readFileSync(abs, "utf8");
  let rows;
  try {
    rows = JSON.parse(raw);
  } catch {
    console.error("JSON 檔必須是陣列或單一物件");
    process.exit(1);
  }

  const list = Array.isArray(rows) ? rows : [rows];

  const { data, error } = await supabase
    .from(table)
    .upsert(list, { onConflict })
    .select();

  if (error) {
    console.error(error.message);
    process.exit(1);
  }
  printJson({ count: data?.length ?? 0, rows: data });
}

const ETYMON_COLS = [
  "tenant_id",
  "created_by",
  "word",
  "category",
  "roots",
  "breakdown",
  "definition",
  "meaning",
  "native_vibe",
  "example",
  "synonym_nuance",
  "usage_warning",
  "memory_hook",
  "phonetic",
  "model",
  "prompt_version",
];

/** 逐筆寫入 etymon_entries（依 tenant_id + word 不分大小寫比對），迴避 expression unique 無法 PostgREST upsert 的問題 */
async function importEtymonFile() {
  const filePath = args[0];
  if (!filePath) {
    console.error("用法: import-etymon <json檔路徑>");
    console.error("檔案內容須為陣列；每筆需含 tenant_id、word 與 12 欄文字欄位。");
    process.exit(1);
  }

  const abs = resolve(process.cwd(), filePath);
  if (!existsSync(abs)) {
    console.error("找不到檔案:", abs);
    process.exit(1);
  }

  let list;
  try {
    list = JSON.parse(readFileSync(abs, "utf8"));
  } catch {
    console.error("JSON 解析失敗");
    process.exit(1);
  }
  if (!Array.isArray(list)) {
    console.error("JSON 頂層必須是陣列");
    process.exit(1);
  }

  let ok = 0;
  let fail = 0;
  const errors = [];

  for (let i = 0; i < list.length; i++) {
    const raw = list[i];
    const row = {};
    for (const k of ETYMON_COLS) {
      if (raw[k] !== undefined) row[k] = raw[k];
    }
    if (!row.tenant_id || !row.word) {
      fail++;
      errors.push({ index: i, reason: "缺 tenant_id 或 word" });
      continue;
    }

    const { data: hit, error: qe } = await supabase
      .from("etymon_entries")
      .select("id")
      .eq("tenant_id", row.tenant_id)
      .ilike("word", row.word)
      .maybeSingle();

    if (qe) {
      fail++;
      errors.push({ index: i, word: row.word, reason: qe.message });
      continue;
    }

    let res;
    if (hit?.id) {
      res = await supabase
        .from("etymon_entries")
        .update(row)
        .eq("id", hit.id)
        .select("id")
        .single();
    } else {
      res = await supabase.from("etymon_entries").insert(row).select("id").single();
    }

    if (res.error) {
      fail++;
      errors.push({ index: i, word: row.word, reason: res.error.message });
    } else {
      ok++;
    }

    if ((i + 1) % 25 === 0) {
      console.error(`… 已處理 ${i + 1}/${list.length}`);
    }
  }

  printJson({
    total: list.length,
    success: ok,
    failed: fail,
    errors: errors.slice(0, 30),
    errors_truncated: errors.length > 30,
  });
}

async function deleteByPk() {
  const table = args[0];
  const pkCol = args[1];
  const pkVal = args[2];

  if (!table || !pkCol || pkVal === undefined) {
    console.error("用法: delete <table> <pk欄位> <pk值>");
    process.exit(1);
  }

  const { data, error } = await supabase
    .from(table)
    .delete()
    .eq(pkCol, pkVal)
    .select();

  if (error) {
    console.error(error.message);
    process.exit(1);
  }
  printJson({ deleted: data?.length ?? 0, rows: data });
}

async function main() {
  switch (cmd) {
    case "peek":
      await peek();
      break;
    case "update":
      await updateByPk();
      break;
    case "upsert":
      await upsertFile();
      break;
    case "delete":
      await deleteByPk();
      break;
    case "import-etymon":
      await importEtymonFile();
      break;
    default:
      console.log(`指令: peek | update | upsert | delete | import-etymon

peek    <table> [limit] [欄位1,欄位2,...]
update  <table> <pk欄> <pk值> '<JSON>'
upsert  <table> <json檔> <onConflict欄位>
delete  <table> <pk欄> <pk值>
import-etymon <json檔>   # 批次寫入 etymon_entries（tenant_id + word）
`);
      process.exit(cmd ? 1 : 0);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
