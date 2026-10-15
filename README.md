# Friday Night IQ — Working Prototype (v0.2)

Friday Night IQ helps coaches upload existing playbook files, organize calls into position-specific play cards, publish weekly installs, and preview a player's study experience. It is a **working Streamlit prototype**, not the secured production app.

## What works now

- Coach dashboard, team workspaces, starter demo data
- Playbook library: create, search, filter, edit, delete plays
- Upload originals (up to 15 MB per file): PDF, DOCX, PPTX, TXT, MD, CSV, PNG, JPEG
- Extract text from PDF pages, PowerPoint slides, Word headings, CSV rows, and text sections; turn a selected section into a coach-reviewed play card
- Position tags (QB, RB, WR, TE, OL, DL, LB, DB, ST, ALL)
- Roster entry and CSV roster import
- Weekly installs: create, assign/adjust plays, delete
- Coach-only player preview: position-filtered install, per-play study status, and scored quizzes
- Coach quiz builder: create and remove multiple-choice questions with verified answers for each play
- Team readiness dashboard: self-marked study status shown separately from latest quiz scores
- Local SQLite storage and complete JSON backup (includes source file bytes)

**Not included:** Production login, coach/player accounts, cross-device sharing, secure permanent cloud database, real automated diagram recognition, automated question generation, or backup restore.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Deploy a demo on Streamlit Community Cloud

1. Create a **new private GitHub repository** named `friday-night-iq` (keep it separate from Saturday Forecast and Sunday Slate).
2. Upload the contents of this directory to the repository, including `app.py`, `storage.py`, `importers.py`, `requirements.txt`, and `.streamlit/config.toml`.
3. In Streamlit Community Cloud, deploy the repo with `app.py` as the entry point.
4. **Only use synthetic/test roster and playbook data.** The app intentionally has no login and local SQLite data can disappear on host restart/redeploy.

For real high-school player use, first move persistence to an authenticated managed database, add secure invite-based roles, and adopt privacy/security controls (including careful handling of student information). The team code in this build is *not* a password.

## Import details

- PDF: one candidate per text-readable page; scanned/diagram-only pages remain only in the original attachment.
- PPTX: one candidate per slide with readable text; image-only slide diagrams are not interpreted.
- DOCX: headings separate sections; paragraphs/tables become text candidates.
- CSV: each row becomes a reviewable candidate.
- TXT/MD: optionally separate candidate sections with a line containing `---`.
- PNG/JPEG: original image preserved; manually enter assignments and play metadata.

Always verify extracted text and write positional responsibilities manually. The system does not guess what a player should do from a diagram.

## Roster CSV format

```csv
name,jersey,position
Sample Quarterback,12,QB
Sample Lineman,74,OL
```

## Project layout

```
app.py               Streamlit interface
storage.py           Database / operations
importers.py         Safe text extraction
.streamlit/config.toml  Dark theme
requirements.txt     Python dependencies
tests/               Core automated tests
```

## Tests

```bash
python -m pytest -q
```

## Data note

`.gitignore` excludes the local `data/` directory and Streamlit secrets. Backups contain roster names and uploaded files. Store them carefully; do not commit backups or real student records into GitHub.

## Try the sample workflow

1. In **Upload Center**, upload `example_uploads/offensive_install.txt`.
2. Select a text section. Assign its position groups, add/verify coaching instructions, and save it to the library.
3. In **Weekly Installs**, create an install and choose the plays you want to teach.
4. In **Quiz Builder**, choose a play and write one or more questions, including four choices and the correct answer.
5. In **Player Preview**, choose a player and install, review the assignment, take the knowledge check, and optionally mark a play "Ready".
6. In **Team Readiness**, choose an install to compare study completion with quiz scores.

**Security & persistence:** These are shared, coach-operated demo views without logins. Quiz results live in the same temporary local SQLite database as the rest of the prototype. Never enter real minors’ information or private team documents, and do not assume any demo data will survive redeployment.

Files under `example_uploads/` are fictional and safe for demonstration.