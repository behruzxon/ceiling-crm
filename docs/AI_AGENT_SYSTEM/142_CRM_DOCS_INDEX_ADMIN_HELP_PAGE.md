> Status: LOCAL FEATURE (F6 of feature/local-agent-web-polish pack).
> Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1 LOG_ONLY: NOT APPLIED.
> Live OpenAI: NOT CALLED. Live Telegram: NOT CALLED. DB writes: NONE.

# 142 — CRM Docs Index / Admin Help Page

## 1. Purpose

Give admins and operators a read-only browse of the
`docs/AI_AGENT_SYSTEM/*.md` runbooks from the CRM web UI. Each doc
gets a one-line summary extracted from its body, grouped by area so
the right runbook is one click away.

## 2. Read-only design

- `GET /help` reads markdown files directly from disk at request
  time and renders `apps/web/templates/help.html`.
- No DB call, no API call, no AI call, no Telegram link.
- Auth: gated by the same `require_dashboard_auth` dependency the
  rest of the CRM web app uses (declared once on `app =
  FastAPI(...)`). The `/help` route adds nothing that bypasses it.
- No POST endpoint, no form, no Send / Save / Apply button.

## 3. Grouping logic

`build_docs_index` extracts the leading number from each filename
(`100_…`, `125_…`, …) and maps it to a fixed area:

| Doc ID range | Area key | Group title |
|---|---|---|
| 1–49 | `foundation` | Foundation / Early docs |
| 50–89 | `ai_agent_stage1_prep` | AI Agent / Stage 1 prep |
| 90–119 | `crm_web_hardening` | CRM / Web / AI hardening |
| 120–129 | `deployment_readiness` | Deployment / Production readiness |
| 130–139 | `audit_local_polish` | Audit / Blocker fixes / Local polish |
| 140+ | `local_feature_docs` | Local feature docs |
| no leading number | `other` | Other |

Empty groups are skipped. Files are sorted ascending by doc ID so
each section reads chronologically.

## 4. Title and summary extraction

- **Title** = first markdown `# H1` heading, falling back to the
  filename stem.
- **Summary** = first non-empty paragraph after the title (skipping
  blockquote prologues and other `#` headings). Capped at **180
  characters**.
- Reading is capped at **8 KiB** per file — enough to find the title
  and the first paragraph, never the whole doc.

## 5. Redaction rules

Both the extracted **title** and **summary** are scrubbed before
they reach the template. A doc whose source contained any of the
markers below comes back with `is_safe=False` and a
`warning="Sensitive marker redacted"` field, and the template
renders a `redacted` badge in red.

Markers stripped:

- Literal substrings: `BOT_TOKEN`, `OPENAI`, `DATABASE_URL`.
- Regex patterns: `postgres://…`, `redis://…`, `Bearer …`,
  `sk-[A-Za-z0-9]{16,}`, Telegram bot tokens (`123456:…`).

Each match is replaced with `[REDACTED]` before the value reaches
the template context.

## 6. Path-traversal defence

- Only the supplied `docs_dir` is iterated (`Path.iterdir()`, **not**
  recursive globbing).
- Sub-directories and dotfiles are skipped.
- Every file resolves to an absolute path; entries whose resolved
  path falls outside `docs_dir.resolve()` are dropped. Symbolic
  links pointing elsewhere cannot leak through.

## 7. Route

`apps/web/main.py`:

```python
_DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "AI_AGENT_SYSTEM"

@app.get("/help", response_class=HTMLResponse)
async def admin_help(request: Request):
    docs_index = build_docs_index(_DOCS_DIR)
    return templates.TemplateResponse(
        "help.html", {"request": request, "docs_index": docs_index}
    )
```

Sidebar entry sits under the **Admin** section in
`apps/web/templates/base.html` with `active_page == "help"`.

## 8. Template

`apps/web/templates/help.html`:

- Three summary cards at the top: total docs, group count, generated
  timestamp.
- One `vp-card` per group, each containing an ordered list of doc
  entries with a left border colour-coded by `is_safe`.
- Each entry shows: `#NN`, title, safe / redacted badge, summary
  (if any), warning line (if redacted), filename and size in bytes.
- No external links. No Telegram links. No Send button. No POST
  form. The page is a static snapshot rebuilt on each request.

## 9. Limitations

- Only top-level `*.md` files under `docs/AI_AGENT_SYSTEM/` are
  surfaced — nested folders are intentionally ignored.
- The summary heuristic favours the first paragraph after the H1;
  docs that lead with long block quotes or YAML front-matter may
  show a short summary or fall back to the filename.
- The page deliberately does **not** render the full markdown body.
  Operators who need the full text follow the listed filename in
  their editor.

## 10. Tests

- `tests/unit/services/test_f6_docs_index_service.py` —
  file-scanning, group ranges, title / summary extraction, secret
  redaction (`BOT_TOKEN`, `OPENAI`, `DATABASE_URL`, `postgres://`,
  `redis://`, `Bearer`, `sk-…`), path-traversal defence, frozen
  dataclass invariants.
- `tests/unit/web/test_f6_admin_help_page.py` — route presence,
  template structure (title, summary cards, group cards, doc title,
  summary, safe / warning badges), sidebar Help link, no Send / no
  POST / no Telegram URL / no raw secrets / no auth-bypass markup.

## 11. Next step

This closes the **F1 → F6** local feature pack. The recommended next
step is a full local regression run + the user's go-ahead to push
`feature/local-agent-web-polish` and open a single PR for review.
