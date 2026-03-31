<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Repository layout (monorepo)

This folder (`kadusella/`) holds the **Next.js + Supabase** slice only.

- **Next**: `kadusella/app/`, `kadusella/public/` — app entry stays under `kadusella/`.
- **Edge**: `kadusella/supabase/migrations`, `kadusella/supabase/functions`.
- **Python / FastAPI / Streamlit**: repository root `streamlit_app/`, `backend/`, `start.py`, `requirements.txt` (not under `kadusella/`).
- **Data & tools (here)**: `kadusella/scripts/`, `kadusella/knowledge_rows.csv`.
- **Content corpus**: repository root `知識/` — path shape is assumed by root `streamlit_app/utils.py`; do not rename casually.
- **Docs & misc (here)**: `kadusella/docs/`, `kadusella/archive/`.
