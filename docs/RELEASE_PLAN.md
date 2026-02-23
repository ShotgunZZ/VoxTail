# VoxTail Open-Source Release Plan

## Status: Files Ready — Manual Steps Remaining

This repo was prepared for open-source release from a private working codebase. All source code, documentation, and templates are in place. The remaining steps require GitHub/Railway account actions.

## What Was Done

### Files Created
- **LICENSE** — MIT, copyright 2026 Shaun Zhang
- **README.md** — Full rewrite with VoxTail branding, two-path setup (Railway + local), API key signup links with free tier notes, ASCII architecture diagram, cost breakdown, API reference, codebase structure, contributing link, attribution
- **CONTRIBUTING.md** — Local dev setup, PR process, code style
- **.env.example** — Updated with all env vars (required + optional) and comments
- **.github/ISSUE_TEMPLATE/bug_report.md** — Bug report template
- **.github/ISSUE_TEMPLATE/feature_request.md** — Feature request template

### Files Cleaned Up
- **.gitignore** — Removed internal-only entries (IMPLEMENTATION_PLAN.md, NEXT_UP.txt, V0.pen, .worktrees/), fixed typo
- **Excluded from copy:** .env, speakers.json, meeting_audio_temp/, pretrained_models/, venv/, __pycache__/, .git/
- **Removed from copy:** docs/plans/, IMPLEMENTATION_PLAN.md, NEXT_UP.txt, V0.pen, .worktrees/

## Remaining Manual Steps

### Step 1: Push to GitHub
```bash
cd voxtail-release
git init
git add .
git commit -m "Initial release"
git remote add origin git@github.com:ShotgunZZ/VoxTail.git
git push -u origin main
```

### Step 2: Railway Template
1. Go to https://railway.com/templates and register this repo as a template
2. Define required env vars: PINECONE_API_KEY, PINECONE_INDEX_NAME, ASSEMBLYAI_API_KEY, OPENAI_API_KEY
3. Copy the template URL
4. Update README.md — replace both `XXXXX` placeholders in the deploy button:
   ```
   [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/XXXXX?referralCode=XXXXX)
   ```

### Step 3: Post-Release
- [ ] Rotate all API keys (AssemblyAI, Pinecone, OpenAI, Slack webhook) — the repo was audited for secrets but rotate as a precaution
- [ ] Add 2-3 screenshots to README (speaker cards, transcript, AI summary)
- [ ] Create "good first issue" labels on GitHub
- [ ] Optional: share on Reddit r/MachineLearning, HN Show, Twitter

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| License | MIT | Maximum adoption, standard for open-source tools |
| Repo strategy | Fresh repo, single commit | Clean history, no risk of leaked secrets |
| API cost model | BYOK (bring your own keys) | No server costs for maintainer, users control spend |
| Invite/admin code | Kept in code, removed from docs | Testing-only feature — works when env vars set, invisible otherwise |
| Deployment | Railway one-click + local setup | Railway handles HTTPS for mobile mic access; local for dev |
| Test suite | Out of scope (good first contributor task) | Ship now, tests are a natural "good first issue" |
| CI/CD | Out of scope | Add when tests exist |
| Docker Compose | Out of scope | `python app.py` is sufficient for local dev |
| Docs site | Out of scope | README is sufficient at launch |

## Architecture Quick Reference

```
Audio → AssemblyAI (diarize) → SpeechBrain ECAPA-TDNN (192-dim embeddings) → Pinecone (match) → Results → OpenAI GPT (summary)
```

- **Backend:** FastAPI + Python, no build step
- **Frontend:** Vanilla JS, ES modules, PWA with service worker
- **ML:** SpeechBrain ECAPA-TDNN on CPU, Silero VAD for speech detection
- **Storage:** Pinecone (vector DB, source of truth), speakers.json (local cache), in-memory sessions (1hr TTL)
- **Integrations:** Slack webhooks, Google Drive via service account

See [CLAUDE.md](../CLAUDE.md) for full technical reference including all endpoints, data flows, confidence levels, and implementation details.
