"""SQLite data layer for the Friday Night IQ local prototype.

The SQLite database is suitable for development / local use only. Streamlit
Community Cloud filesystem storage is ephemeral and not appropriate for real
team data or a shared multi-user deployment.
"""
from __future__ import annotations

import os
import sqlite3
import json
import secrets
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "data" / "friday_night_iq.sqlite3"


def db_path() -> Path:
    return Path(os.environ.get("FRIDAY_NIGHT_IQ_DB", str(DEFAULT_DB)))


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            season TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            jersey TEXT NOT NULL DEFAULT '',
            position TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            filebytes BLOB NOT NULL,
            segments_json TEXT NOT NULL,
            warnings_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            unit TEXT NOT NULL,
            positions TEXT NOT NULL,
            formation TEXT NOT NULL DEFAULT '',
            situation TEXT NOT NULL DEFAULT '',
            assignment TEXT NOT NULL DEFAULT '',
            coaching_points TEXT NOT NULL DEFAULT '',
            source_upload_id INTEGER REFERENCES uploads(id) ON DELETE SET NULL,
            source_segment TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS installs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            opponent TEXT NOT NULL DEFAULT '',
            week TEXT NOT NULL DEFAULT '',
            install_date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS install_plays (
            install_id INTEGER NOT NULL REFERENCES installs(id) ON DELETE CASCADE,
            play_id INTEGER NOT NULL REFERENCES plays(id) ON DELETE CASCADE,
            PRIMARY KEY (install_id, play_id)
        );
        CREATE TABLE IF NOT EXISTS progress (
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            install_id INTEGER NOT NULL REFERENCES installs(id) ON DELETE CASCADE,
            play_id INTEGER NOT NULL REFERENCES plays(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'Not started',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (player_id, install_id, play_id)
        );
        CREATE INDEX IF NOT EXISTS idx_plays_team ON plays(team_id);
        CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
        CREATE INDEX IF NOT EXISTS idx_installs_team ON installs(team_id);
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            play_id INTEGER NOT NULL REFERENCES plays(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK(correct_option IN ('A','B','C','D')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            install_id INTEGER NOT NULL REFERENCES installs(id) ON DELETE CASCADE,
            play_id INTEGER NOT NULL REFERENCES plays(id) ON DELETE CASCADE,
            correct_count INTEGER NOT NULL,
            question_count INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_quiz_questions_team_play ON quiz_questions(team_id,play_id);
        CREATE INDEX IF NOT EXISTS idx_quiz_attempts_team_player_install
            ON quiz_attempts(team_id,player_id,install_id,play_id,id);
        """)
        if db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0:
            code = "DEMO" + secrets.token_hex(2).upper()
            t = db.execute("INSERT INTO teams (name,season,code) VALUES (?,?,?)",
                           ("Demo Wildcats", "2026", code)).lastrowid
            for n, j, p in [("Jordan Walker", "12", "QB"), ("Taylor Brooks", "74", "OL"),
                            ("Avery Davis", "22", "RB"), ("Morgan Lee", "8", "WR")]:
                db.execute("INSERT INTO players(team_id,name,jersey,position) VALUES (?,?,?,?)",(t,n,j,p))
            examples = [
                ("Inside Zone Right", "Offense", "OL,RB,QB", "Doubles", "1st & 10",
                 "OL: Covered/uncovered zone steps, climb to linebacker. RB: Press play-side A gap; read first down lineman past center. QB: Mesh and carry out fake.",
                 "Vertical first steps; stay on double teams until linebacker commits."),
                ("Mesh Concept", "Offense", "QB,WR,RB", "Trips Right", "3rd & medium",
                 "WR: Shallow cross at 5 yards. QB: Identify man/zone; work mesh to sit route, then checkdown.",
                 "Receivers communicate traffic; throw on time."),
                ("Cover 3 Sky", "Defense", "DB,LB,DL", "4-2-5", "Base downs",
                 "DB: Rotate to deep thirds/underneath zones. LB: Hook/curl drops. DL: Maintain rush lanes.",
                 "Communicate motion and formation strength before snap.")
            ]
            for title, unit, positions, form, sit, assignment, points in examples:
                db.execute("""INSERT INTO plays(team_id,title,unit,positions,formation,situation,assignment,coaching_points)
                    VALUES (?,?,?,?,?,?,?,?)""",(t,title,unit,positions,form,sit,assignment,points))


def rows(sql: str, args: tuple=()) -> list[dict]:
    with connect() as db:
        return [dict(r) for r in db.execute(sql,args).fetchall()]


def one(sql: str, args: tuple=()) -> dict | None:
    with connect() as db:
        r=db.execute(sql,args).fetchone()
        return dict(r) if r else None


def write(sql: str,args: tuple=()) -> int:
    with connect() as db:
        result=db.execute(sql,args)
        return result.lastrowid or 0


def create_team(name: str,season: str):
    for _ in range(4):
        try:
            return write("INSERT INTO teams(name,season,code) VALUES(?,?,?)",(name.strip(),season.strip(),secrets.token_hex(4).upper()))
        except sqlite3.IntegrityError:
            pass
    raise RuntimeError("Could not generate unique team code")


def create_install(team_id:int,title:str,opponent:str,week:str,install_date:str,notes:str,play_ids:list[int]):
    with connect() as db:
        ident = db.execute("INSERT INTO installs(team_id,title,opponent,week,install_date,notes) VALUES (?,?,?,?,?,?)",
            (team_id,title,opponent,week,install_date,notes)).lastrowid
        # Validate each play belongs to selected team; never attach another team's play.
        for p in set(play_ids):
            if db.execute("SELECT 1 FROM plays WHERE id=? AND team_id=?",(p,team_id)).fetchone():
                db.execute("INSERT INTO install_plays(install_id,play_id) VALUES(?,?)",(ident,p))
    return ident


def update_install_plays(install_id:int,team_id:int,play_ids:list[int]):
    with connect() as db:
        if not db.execute("SELECT 1 FROM installs WHERE id=? AND team_id=?",(install_id,team_id)).fetchone():
            raise ValueError("Install does not belong to this team")
        db.execute("DELETE FROM install_plays WHERE install_id=?",(install_id,))
        valid=db.execute("SELECT id FROM plays WHERE team_id=?",(team_id,)).fetchall()
        allowed={x[0] for x in valid}
        for p in set(play_ids)&allowed:
            db.execute("INSERT INTO install_plays(install_id,play_id) VALUES (?,?)",(install_id,p))


def player_install_plays(team_id:int,player_id:int,install_id:int) -> list[dict]:
    """Never expose plays assigned to another team or to unrelated positions."""
    player=one("SELECT * FROM players WHERE id=? AND team_id=?",(player_id,team_id))
    if not player:
        return []
    return [p for p in rows("""SELECT p.*,COALESCE(s.status,'Not started') AS study_status
      FROM plays p JOIN install_plays ip ON ip.play_id=p.id
      JOIN installs i ON i.id=ip.install_id
      LEFT JOIN progress s ON s.player_id=? AND s.install_id=i.id AND s.play_id=p.id
      WHERE i.id=? AND i.team_id=? AND p.team_id=? ORDER BY p.unit,p.title""",
      (player_id,install_id,team_id,team_id)) if "ALL" in p['positions'].split(',') or player['position'] in p['positions'].split(',')]


def set_progress(team_id:int,player_id:int,install_id:int,play_id:int,status:str):
    if status not in ("Not started","Studying","Ready"):
        raise ValueError("Invalid status")
    available={p['id'] for p in player_install_plays(team_id,player_id,install_id)}
    if play_id not in available:
        raise ValueError("Play not assigned to this player")
    with connect() as db:
        db.execute("""INSERT INTO progress(player_id,install_id,play_id,status) VALUES(?,?,?,?)
        ON CONFLICT(player_id,install_id,play_id) DO UPDATE SET status=excluded.status,
        updated_at=CURRENT_TIMESTAMP""",(player_id,install_id,play_id,status))


def quiz_questions(team_id: int, play_id: int) -> list[dict]:
    """Return only a team's own questions for a play."""
    return rows("""SELECT q.* FROM quiz_questions q JOIN plays p ON p.id=q.play_id
        WHERE q.team_id=? AND q.play_id=? AND p.team_id=? ORDER BY q.id""",
        (team_id, play_id, team_id))


def add_quiz_question(team_id: int, play_id: int, prompt: str,
                      options: list[str], correct_option: str) -> int:
    """Questions and answers are coach-authored, never invented from playbook text."""
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>500:
        raise ValueError("Enter a question (500 characters maximum)")
    if len(options)!=4 or not all(isinstance(x,str) and 0<len(x.strip())<=250 for x in options):
        raise ValueError("Enter four answer choices (250 characters maximum each)")
    cleaned=[x.strip() for x in options]
    if len({x.casefold() for x in cleaned})!=4:
        raise ValueError("Answer choices must be different")
    if correct_option not in ('A','B','C','D'):
        raise ValueError("Choose the correct answer")
    with connect() as db:
        if not db.execute("SELECT 1 FROM plays WHERE id=? AND team_id=?",(play_id,team_id)).fetchone():
            raise ValueError("Play does not belong to this team")
        return db.execute("""INSERT INTO quiz_questions
            (team_id,play_id,question_text,option_a,option_b,option_c,option_d,correct_option)
            VALUES(?,?,?,?,?,?,?,?)""",
            (team_id,play_id,prompt.strip(),*cleaned,correct_option)).lastrowid


def delete_quiz_question(team_id: int, question_id: int):
    with connect() as db:
        db.execute("DELETE FROM quiz_questions WHERE team_id=? AND id=?",(team_id,question_id))


def last_quiz_attempt(team_id: int, player_id: int, install_id: int, play_id: int) -> dict | None:
    return one("""SELECT a.* FROM quiz_attempts a
        JOIN players p ON p.id=a.player_id AND p.team_id=a.team_id
        JOIN installs i ON i.id=a.install_id AND i.team_id=a.team_id
        JOIN plays pl ON pl.id=a.play_id AND pl.team_id=a.team_id
        WHERE a.team_id=? AND a.player_id=? AND a.install_id=? AND a.play_id=?
        ORDER BY a.id DESC LIMIT 1""", (team_id,player_id,install_id,play_id))


def submit_quiz(team_id: int, player_id: int, install_id: int,
                play_id: int, answers: dict[int, str]) -> dict:
    """Grade server-side against coach-defined answers, after checking team and position."""
    if play_id not in {p['id'] for p in player_install_plays(team_id,player_id,install_id)}:
        raise ValueError("This play is not assigned to this player")
    with connect() as db:
        questions=[dict(q) for q in db.execute("""SELECT q.* FROM quiz_questions q
            JOIN plays p ON p.id=q.play_id AND p.team_id=q.team_id
            WHERE q.team_id=? AND q.play_id=? ORDER BY q.id""", (team_id,play_id)).fetchall()]
        if not questions:
            raise ValueError("There is no quiz for this play")
        q_ids={q['id'] for q in questions}
        if set(answers)!=q_ids or any(answers[q] not in ('A','B','C','D') for q in q_ids):
            raise ValueError("Answer every question before submitting")
        correct=sum(answers[q['id']]==q['correct_option'] for q in questions)
        count=len(questions)
        db.execute("""INSERT INTO quiz_attempts
            (team_id,player_id,install_id,play_id,correct_count,question_count)
            VALUES(?,?,?,?,?,?)""", (team_id,player_id,install_id,play_id,correct,count))
    return {"correct":correct,"total":count,"percent":round(100*correct/count)}


def team_readiness(team_id: int, install_id: int) -> list[dict]:
    if not one("SELECT 1 FROM installs WHERE id=? AND team_id=?",(install_id,team_id)):
        return []
    output=[]
    for player in rows("SELECT * FROM players WHERE team_id=? ORDER BY position,name",(team_id,)):
        assigned=player_install_plays(team_id,player['id'],install_id)
        attempts=[last_quiz_attempt(team_id,player['id'],install_id,p['id']) for p in assigned]
        attempts=[a for a in attempts if a]
        output.append({"player":player['name'],"position":player['position'],
                       "assigned":len(assigned),"ready":sum(p['study_status']=='Ready' for p in assigned),
                       "quizzes_taken":len(attempts),
                       "average_quiz_score":round(sum(100*a['correct_count']/a['question_count']
                           for a in attempts)/len(attempts)) if attempts else None})
    return output


def export_team(team_id: int) -> bytes:
    """Portable backup including original upload bytes; should be stored securely."""
    import base64
    t=one("SELECT * FROM teams WHERE id=?",(team_id,))
    if not t: raise ValueError("Team not found")
    uploads=rows("SELECT * FROM uploads WHERE team_id=?",(team_id,))
    for r in uploads:
        r['filebytes']=base64.b64encode(r['filebytes']).decode('ascii')
    payload={
        "format":"friday-night-iq-backup-v1",
        "team":t,
        "players":rows("SELECT * FROM players WHERE team_id=?",(team_id,)),
        "plays":rows("SELECT * FROM plays WHERE team_id=?",(team_id,)),
        "uploads":uploads,
        "installs":rows("SELECT * FROM installs WHERE team_id=?",(team_id,)),
        "install_plays":rows("""SELECT ip.* FROM install_plays ip JOIN installs i ON i.id=ip.install_id WHERE i.team_id=?""",(team_id,)),
        "progress":rows("""SELECT pr.* FROM progress pr JOIN players p ON p.id=pr.player_id WHERE p.team_id=?""",(team_id,)),
        "quiz_questions":rows("SELECT * FROM quiz_questions WHERE team_id=?",(team_id,)),
        "quiz_attempts":rows("SELECT * FROM quiz_attempts WHERE team_id=?",(team_id,)),
    }
    return json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')
