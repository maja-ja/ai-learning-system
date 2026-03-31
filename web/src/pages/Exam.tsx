import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { FolderOpen, Lock, LogOut, Plus, Save, Search } from "lucide-react";
import type { ExamSubject } from "../types";
import {
  clearExamToken,
  examLogin,
  fetchExamNote,
  fetchExamTree,
  getExamToken,
  saveExamNote,
  searchExamLocal,
} from "../lib/api";

export default function Exam() {
  const [token, setTokenState] = useState<string | null>(() => getExamToken());
  const [pw, setPw] = useState("");
  const [loginErr, setLoginErr] = useState<string | null>(null);
  const [tree, setTree] = useState<ExamSubject[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [examEditAllowed, setExamEditAllowed] = useState(true);

  const loadTree = useCallback(async () => {
    setLoadErr(null);
    try {
      const { subjects, examEditAllowed: can } = await fetchExamTree();
      setTree(subjects);
      setExamEditAllowed(can);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "載入失敗";
      if (msg === "UNAUTHORIZED") {
        setTokenState(null);
        setLoginErr("憑證已失效，請重新登入");
      } else setLoadErr(msg);
    }
  }, []);

  useEffect(() => {
    if (token) loadTree();
  }, [token, loadTree]);

  const onLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginErr(null);
    try {
      const { examEditAllowed: can } = await examLogin(pw);
      setExamEditAllowed(can);
      setTokenState(getExamToken());
      setPw("");
    } catch (err) {
      setLoginErr(err instanceof Error ? err.message : "登入失敗");
    }
  };

  const logout = () => {
    clearExamToken();
    setTokenState(null);
    setTree([]);
  };

  if (!token) {
    return (
      <div className="mx-auto max-w-md space-y-6 pt-8">
        <div className="text-center space-y-2">
          <Lock className="mx-auto h-10 w-10 text-accent-glow" />
          <h1 className="text-2xl font-bold text-white">學測資料庫</h1>
          <p className="text-sm text-ink-400">
            輸入與環境變數 <code className="text-ink-300">APP_PASSWORD</code>{" "}
            相同的密碼以瀏覽本地「知識」目錄。
          </p>
        </div>
        <form
          onSubmit={onLogin}
          className="glass-panel space-y-4 p-6"
        >
          {loginErr && (
            <p className="text-sm text-red-300">{loginErr}</p>
          )}
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="密碼"
            className="w-full rounded-xl border border-white/10 bg-ink-900/60 px-4 py-3 text-sm text-white"
          />
          <button
            type="submit"
            className="w-full rounded-xl bg-accent py-3 text-sm font-medium text-white hover:bg-accent-dim"
          >
            解鎖
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">學測資料庫</h1>
          <p className="text-ink-400 text-sm mt-1">
            本地 Markdown 樹狀瀏覽 · Google Sheet 單字庫請另用試算表或後續串接
          </p>
          {!examEditAllowed && (
            <p className="text-amber-200/90 text-sm mt-2 rounded-lg border border-amber-500/30 bg-amber-950/40 px-3 py-2">
              目前為公開 HTTPS：學測區僅供瀏覽。若要新增或修改 note.md，請在本機開啟{" "}
              <code className="text-ink-200">http://127.0.0.1:8000</code>（或設定後端{" "}
              <code className="text-ink-200">EXAM_ALLOW_HTTPS_EDIT=true</code>）。
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={logout}
          data-track="exam/logout"
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-ink-300 hover:bg-white/5"
        >
          <LogOut className="h-4 w-4" />
          登出
        </button>
      </div>

      {loadErr && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-amber-100 text-sm">
          {loadErr}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 glass-panel p-4 max-h-[75vh] overflow-y-auto">
          <h2 className="text-sm font-semibold text-ink-300 flex items-center gap-2 mb-3">
            <FolderOpen className="h-4 w-4" /> 目錄
          </h2>
          <TreeView tree={tree} />
        </div>
        <div className="lg:col-span-2 space-y-4">
          <SearchPanel subjects={tree.map((s) => s.name)} />
          <CreateNotePanel editAllowed={examEditAllowed} onCreated={loadTree} />
          <NotePanel editAllowed={examEditAllowed} />
        </div>
      </div>
    </div>
  );
}

function TreeView({ tree }: { tree: ExamSubject[] }) {
  return (
    <ul className="space-y-1 text-sm">
      {tree.map((sub) => (
        <li key={sub.name}>
          <span className="font-medium text-white">{sub.name}</span>
          <ul className="ml-3 mt-1 space-y-2 border-l border-white/10 pl-3">
            {sub.chapters.map((ch) => (
              <li key={ch.name}>
                <span className="text-ink-400">{ch.name}</span>
                <ul className="ml-2 mt-1 space-y-0.5">
                  {ch.units.map((u) => (
                    <li key={u.name}>
                      <button
                        type="button"
                        onClick={() => {
                          window.dispatchEvent(
                            new CustomEvent("exam-open-note", {
                              detail: {
                                subject: sub.name,
                                chapter: ch.name,
                                unit: u.name,
                              },
                            })
                          );
                        }}
                        className="text-left text-accent-glow hover:underline"
                      >
                        {u.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

function CreateNotePanel({
  editAllowed,
  onCreated,
}: {
  editAllowed: boolean;
  onCreated: () => void;
}) {
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");
  const [unit, setUnit] = useState("");
  const [content, setContent] = useState("# 標題\n\n");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editAllowed) return;
    if (!subject.trim() || !chapter.trim() || !unit.trim()) {
      setMsg("請填寫科目、章節、單元");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await saveExamNote(subject.trim(), chapter.trim(), unit.trim(), content);
      setMsg("已建立 note.md");
      onCreated();
    } catch {
      setMsg("建立失敗");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-4 space-y-3">
      <h2 className="text-sm font-semibold text-ink-300 flex items-center gap-2">
        <Plus className="h-4 w-4" /> 新增本地單元（note.md）
      </h2>
      {!editAllowed ? (
        <p className="text-sm text-ink-500">公開站已停用此區塊的建立功能。</p>
      ) : (
        <form onSubmit={submit} className="grid sm:grid-cols-3 gap-2">
          <input
            required
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="科目"
            className="rounded-lg border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white"
          />
          <input
            required
            value={chapter}
            onChange={(e) => setChapter(e.target.value)}
            placeholder="章節"
            className="rounded-lg border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white"
          />
          <input
            required
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            placeholder="單元資料夾名稱"
            className="rounded-lg border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white"
          />
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={4}
            className="sm:col-span-3 rounded-lg border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white font-mono"
          />
          <button
            type="submit"
            disabled={busy}
            className="sm:col-span-3 rounded-lg bg-emerald-700/80 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            {busy ? "儲存中…" : "建立"}
          </button>
        </form>
      )}
      {msg && <p className="text-xs text-ink-400">{msg}</p>}
    </div>
  );
}

function SearchPanel({ subjects }: { subjects: string[] }) {
  const [q, setQ] = useState("");
  const [sub, setSub] = useState("");
  const [hits, setHits] = useState<
    { subject: string; chapter: string; unit: string; snippet: string }[]
  >([]);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try {
      const r = await searchExamLocal(q.trim(), sub || undefined);
      setHits(r);
    } catch {
      setHits([]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-4 space-y-3">
      <h2 className="text-sm font-semibold text-ink-300 flex items-center gap-2">
        <Search className="h-4 w-4" /> 搜尋本地 note.md
      </h2>
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="關鍵字"
          className="flex-1 rounded-lg border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white"
        />
        <select
          value={sub}
          onChange={(e) => setSub(e.target.value)}
          className="rounded-lg border border-white/10 bg-ink-900/60 px-3 py-2 text-sm text-white"
        >
          <option value="">全部科目</option>
          {subjects.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={run}
          disabled={busy}
          data-track="exam/search_run"
          className="rounded-lg bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/15 disabled:opacity-50"
        >
          {busy ? "…" : "搜尋"}
        </button>
      </div>
      <ul className="space-y-2 max-h-48 overflow-y-auto text-xs">
        {hits.map((h, i) => (
          <li key={i} className="rounded-lg bg-ink-800/40 p-2 border border-white/5">
            <button
              type="button"
              className="text-accent-glow font-medium hover:underline"
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("exam-open-note", {
                    detail: {
                      subject: h.subject,
                      chapter: h.chapter,
                      unit: h.unit,
                    },
                  })
                )
              }
            >
              {h.subject} / {h.chapter} / {h.unit}
            </button>
            <p className="text-ink-500 mt-1 line-clamp-2">{h.snippet}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NotePanel({ editAllowed }: { editAllowed: boolean }) {
  const [path, setPath] = useState<{
    subject: string;
    chapter: string;
    unit: string;
  } | null>(null);
  const [md, setMd] = useState("");
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent).detail as {
        subject: string;
        chapter: string;
        unit: string;
      };
      setPath(d);
      setEdit(false);
      setMsg(null);
    };
    window.addEventListener("exam-open-note", h);
    return () => window.removeEventListener("exam-open-note", h);
  }, []);

  useEffect(() => {
    if (!editAllowed) setEdit(false);
  }, [editAllowed]);

  useEffect(() => {
    if (!path) {
      setMd("");
      setDraft("");
      return;
    }
    let ok = true;
    setLoading(true);
    fetchExamNote(path.subject, path.chapter, path.unit)
      .then((c) => {
        if (ok) {
          setMd(c);
          setDraft(c);
        }
      })
      .catch(() => {
        if (ok) {
          setMd("");
          setDraft("");
          setMsg("讀取失敗");
        }
      })
      .finally(() => {
        if (ok) setLoading(false);
      });
    return () => {
      ok = false;
    };
  }, [path]);

  const save = async () => {
    if (!path) return;
    setMsg(null);
    try {
      await saveExamNote(path.subject, path.chapter, path.unit, draft);
      setMd(draft);
      setEdit(false);
      setMsg("已儲存");
    } catch {
      setMsg("儲存失敗");
    }
  };

  if (!path) {
    return (
      <div className="glass-panel min-h-[280px] p-6 flex items-center justify-center text-ink-500 text-sm">
        從左側目錄或搜尋結果點選一則單元以開啟 note.md
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink-300">
          {path.subject} · {path.chapter} · {path.unit}
        </p>
        <div className="flex gap-2">
          {editAllowed && (
            <button
              type="button"
              onClick={() => {
                setEdit(!edit);
                setDraft(md);
              }}
              data-track="exam/note_edit_toggle"
              className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-ink-200 hover:bg-white/5"
            >
              {edit ? "取消編輯" : "編輯"}
            </button>
          )}
          {editAllowed && edit && (
            <button
              type="button"
              onClick={save}
              data-track="exam/note_save"
              className="inline-flex items-center gap-1 rounded-lg bg-emerald-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600"
            >
              <Save className="h-3.5 w-3.5" /> 儲存
            </button>
          )}
        </div>
      </div>
      {msg && <p className="text-xs text-accent-glow">{msg}</p>}
      {loading ? (
        <p className="text-sm text-ink-500">載入中…</p>
      ) : edit && editAllowed ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="w-full min-h-[360px] rounded-xl border border-white/10 bg-ink-950/60 p-4 font-mono text-sm text-ink-100"
        />
      ) : (
        <article className="prose prose-invert prose-sm max-w-none prose-headings:text-white prose-p:text-ink-200 prose-a:text-accent-glow">
          <ReactMarkdown>{md || "（空白）"}</ReactMarkdown>
        </article>
      )}
    </div>
  );
}
