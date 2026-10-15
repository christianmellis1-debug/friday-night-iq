"""Friday Night IQ — coach-led playbook & weekly install prototype.

Run locally with: streamlit run app.py

SECURITY: This MVP has no player authentication or shared production database.
The Player Preview is explicitly a *coach demo*, not a secure student portal.
"""
from __future__ import annotations

import csv
from datetime import date
from io import StringIO
import json
from pathlib import Path
import streamlit as st

from importers import SUPPORTED, extract, MAX_UPLOAD_MB
import storage as store

st.set_page_config(page_title="Friday Night IQ",page_icon="🏈",layout="wide",initial_sidebar_state="expanded")
store.init_db()

POSITIONS=["QB","RB","WR","TE","OL","DL","LB","DB","ST","ALL"]
UNITS=["Offense","Defense","Special Teams"]
NAV=["Dashboard","Playbook Library","Upload Center","Weekly Installs","Quiz Builder","Roster","Player Preview","Team Readiness","Data & Settings"]

st.markdown("""
<style>
  .stApp { background: radial-gradient(circle at 80% -10%,#1b2d30 0%,#0d1318 38%); }
  [data-testid="stSidebar"] { background: #111c24; border-right: 1px solid #243641; }
  .block-container { padding-top:1.4rem; padding-bottom: 4rem; max-width: 1280px; }
  h1,h2,h3 { letter-spacing:-.035em; }
  h1 { font-weight:800; }
  [data-testid="stMetric"] { background:#142029; border:1px solid #30434c; border-radius:14px; padding:16px 18px; }
  [data-testid="stMetricLabel"] { color:#afbfc6; }
  div[data-testid="stExpander"] { background:#121e25; border:1px solid #293b44; border-radius:12px; margin-bottom:10px; }
  div.stButton > button[kind="primary"] { background:#e3b04b; color:#142029; border:none; font-weight:750; }
  div.stButton > button { border-radius:9px; }
  .eyebrow { color:#e3b04b; font-size:12px; text-transform:uppercase; letter-spacing:.17em; font-weight:800; }
  .subtle { color:#a7bcc5; }
  .hero { background:linear-gradient(110deg,#1e3138,#17232d 70%); border:1px solid #34515a; border-radius:18px; padding:28px 30px; margin-bottom:24px; }
  .hero h1 { margin:.1em 0; color:#faf7ef; }
  .hero p { color:#bad0d2; margin-bottom:0; }
  .tag { display:inline-block;background:#26393b;color:#efc873;border-radius:30px;padding:4px 10px;font-size:12px;font-weight:700;margin-right:5px; }
  footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


def headline(label,subtitle):
    st.title(label)
    st.caption(subtitle)


def full_positions(p):
    return ", ".join(p.split(','))


def position_match(play, pos):
    keys=play['positions'].split(',')
    return pos in keys or 'ALL' in keys


def edit_play_form(team_id, item, key):
    current=[p for p in item['positions'].split(',') if p in POSITIONS]
    with st.form(f"play_edit_{key}"):
        c1,c2=st.columns(2)
        title=c1.text_input("Play name",value=item['title'])
        unit=c2.selectbox("Unit",UNITS,index=UNITS.index(item['unit']) if item['unit'] in UNITS else 0)
        pos=st.multiselect("Position groups",POSITIONS,default=current)
        a,b=st.columns(2)
        formation=a.text_input("Formation / front",value=item['formation'])
        situation=b.text_input("Situation",value=item['situation'])
        assignment=st.text_area("Position responsibilities",value=item['assignment'],height=115)
        points=st.text_area("Coaching points",value=item['coaching_points'],height=90)
        save=st.form_submit_button("Save play",type="primary")
        if save:
            if not title.strip() or not pos:
                st.error("Enter a play name and at least one position group.")
            else:
                store.write("""UPDATE plays SET title=?,unit=?,positions=?,formation=?,situation=?,assignment=?,coaching_points=?
                     WHERE id=? AND team_id=?""",(title.strip(),unit,','.join(pos),formation,situation,assignment,points,item['id'],team_id))
                st.success("Play saved.")
                st.rerun()


# Widget state cannot be changed after its widget is rendered in the same run.
if 'pending_section' in st.session_state:
    st.session_state['section'] = st.session_state.pop('pending_section')
if 'pending_team' in st.session_state:
    st.session_state['team_id'] = st.session_state.pop('pending_team')

with st.sidebar:
    st.markdown("### 🏈 FRIDAY NIGHT IQ")
    st.caption("PLAYBOOK → INSTALL → LEARN → FRIDAY READY")
    team_list=store.rows("SELECT * FROM teams ORDER BY id")
    names={int(t['id']):f"{t['name']} · {t['season']}" for t in team_list}
    selected=st.selectbox("Team workspace",list(names),format_func=lambda k:names[k],key="team_id")
    st.divider()
    st.radio("Navigate",NAV,key="section",label_visibility="collapsed")
    st.divider()
    with st.expander("＋ Add team"):
        with st.form("add_team_form",clear_on_submit=True):
            n=st.text_input("Team name",placeholder="e.g., Central Tigers")
            s=st.text_input("Season",value="2027")
            if st.form_submit_button("Create workspace"):
                if n.strip() and s.strip():
                    ident=store.create_team(n,s)
                    st.session_state['pending_team']=ident
                    st.success("Workspace created.")
                    st.rerun()
                else:
                    st.error("Enter a team and season.")
    st.caption("Prototype · Local-first database · No player accounts")

team=store.one("SELECT * FROM teams WHERE id=?",(selected,))
section=st.session_state['section']
team_id=team['id']
plays=store.rows("SELECT * FROM plays WHERE team_id=? ORDER BY unit,title",(team_id,))
players=store.rows("SELECT * FROM players WHERE team_id=? ORDER BY name",(team_id,))
installs=store.rows("SELECT * FROM installs WHERE team_id=? ORDER BY install_date DESC,id DESC",(team_id,))
uploads=store.rows("SELECT id,filename,filetype,created_at FROM uploads WHERE team_id=? ORDER BY id DESC",(team_id,))

if section=="Dashboard":
    st.markdown(f'<div class="hero"><span class="eyebrow">Coach command center</span><h1>Friday Night IQ</h1><p>Build smarter installs. Help every player know their assignment.</p></div>',unsafe_allow_html=True)
    st.subheader(team['name'])
    st.caption(f"Season {team['season']} · Workspace code {team['code']} (identifier only, not a secure login)")
    a,b,c,d=st.columns(4)
    a.metric("Plays in library",len(plays))
    b.metric("Rostered players",len(players))
    c.metric("Weekly installs",len(installs))
    d.metric("Uploaded files",len(uploads))
    st.markdown("### Get ready for Friday")
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown("**1 · Build your library**")
        st.write("Add individual plays or turn document sections into draft play cards.")
        if st.button("Open playbook library",use_container_width=True):
            st.session_state['pending_section']="Playbook Library"; st.rerun()
    with c2:
        st.markdown("**2 · Publish the install**")
        st.write("Choose this week's opponent, date, and teaching priorities.")
        if st.button("Create weekly install",use_container_width=True):
            st.session_state['pending_section']="Weekly Installs"; st.rerun()
    with c3:
        st.markdown("**3 · See player experience**")
        st.write("Preview position-specific assignments and study completion.")
        if st.button("Preview player learning",use_container_width=True):
            st.session_state['pending_section']="Player Preview"; st.rerun()
    st.divider()
    st.markdown("### Most recent installs")
    if installs:
        for ins in installs[:4]:
            count=store.one("SELECT COUNT(*) n FROM install_plays WHERE install_id=?",(ins['id'],))['n']
            with st.container(border=True):
                st.write(f"**{ins['title']}**  ·  {ins['install_date']}")
                st.caption(f"Opponent: {ins['opponent'] or 'Not specified'} · {count} plays assigned")
    else: st.info("No weekly installs yet. Create one once your playbook has plays.")
    st.info("Demo data is included to explore the workflow. This prototype does not yet have secure coach/player logins or permanent cloud storage.",icon="ℹ️")

elif section=="Playbook Library":
    headline("Playbook Library","A single, organized source of truth for your calls and responsibilities.")
    with st.expander("＋ Create play manually",expanded=not bool(plays)):
        with st.form("new_manual_play",clear_on_submit=True):
            a,b=st.columns(2)
            title=a.text_input("Play name",placeholder="Counter GT")
            unit=b.selectbox("Unit",UNITS)
            positions=st.multiselect("Who should study this?",POSITIONS,default=["OL"])
            c,d=st.columns(2)
            form=c.text_input("Formation / front",placeholder="Doubles Left")
            sit=d.text_input("Situation",placeholder="2nd & short")
            assignment=st.text_area("Position responsibilities",placeholder="OL: Guard pulls to kick...\nRB: Press first step then follow puller...")
            coaching=st.text_area("Coaching points",placeholder="Eyes on linebacker, square shoulders...")
            if st.form_submit_button("Add play",type="primary"):
                if not title.strip() or not positions: st.error("A play name and position are required.")
                else:
                    store.write("""INSERT INTO plays(team_id,title,unit,positions,formation,situation,assignment,coaching_points)
                       VALUES(?,?,?,?,?,?,?,?)""",(team_id,title.strip(),unit,','.join(positions),form,sit,assignment,coaching))
                    st.success("Play added."); st.rerun()
    a,b=st.columns([2,1])
    lookup=a.text_input("Find a play",placeholder="Search by name, formation, or responsibility")
    unit_filter=b.selectbox("Unit",["All units"]+UNITS)
    position_filter=st.selectbox("Position group",["All positions"]+POSITIONS)
    shown=[p for p in plays if (not lookup or lookup.lower() in ' '.join(str(p.get(k,'')) for k in ('title','formation','assignment','coaching_points')).lower())
           and (unit_filter=="All units" or p['unit']==unit_filter)
           and (position_filter=="All positions" or position_match(p,position_filter))]
    st.caption(f"Showing {len(shown)} of {len(plays)} plays")
    for p in shown:
        with st.expander(f"{p['title']}   ·   {p['unit']}   ·   {full_positions(p['positions'])}"):
            m,n=st.columns(2)
            m.write(f"**Formation/front:** {p['formation'] or '—'}")
            n.write(f"**Situation:** {p['situation'] or '—'}")
            st.write("**Position assignments**")
            st.write(p['assignment'] or "No responsibilities recorded yet.")
            st.write("**Coaching points**")
            st.write(p['coaching_points'] or "—")
            if p['source_upload_id']:
                source=next((u for u in uploads if u['id']==p['source_upload_id']),None)
                st.caption("Imported source: "+(source['filename'] if source else "Source removed"))
            if st.toggle("Edit this play",key=f"edit_toggle_{p['id']}"):
                edit_play_form(team_id,p,p['id'])
            delete=st.checkbox("I understand this will permanently remove this play (including install associations).",key=f"confirm_del_{p['id']}")
            if st.button("Delete play",key=f"del_{p['id']}",disabled=not delete):
                store.write("DELETE FROM plays WHERE id=? AND team_id=?",(p['id'],team_id)); st.rerun()
    if not shown: st.info("No matching plays. Try clearing the filters or creating one above.")

elif section=="Upload Center":
    headline("Upload Center","Bring your existing files; keep your diagrams and create reviewable play cards.")
    st.markdown("**Supported:** PDF, Word (.docx), PowerPoint (.pptx), TXT, Markdown, CSV, PNG and JPEG")
    st.caption("Text can be extracted from readable documents. Images and diagram-only pages are preserved but are not automatically interpreted.")
    f=st.file_uploader(f"Select a playbook (up to {MAX_UPLOAD_MB} MB)",type=sorted(SUPPORTED),key="playbook_upload")
    if f and st.button("Upload and extract sections",type="primary"):
        try:
            content=f.getvalue()
            segments,warnings=extract(f.name,content)
            ident=store.write("""INSERT INTO uploads(team_id,filename,filetype,filebytes,segments_json,warnings_json)
               VALUES(?,?,?,?,?,?)""",(team_id,f.name,Path(f.name).suffix.lower().lstrip('.'),content,json.dumps(segments),json.dumps(warnings)))
            st.session_state['latest_upload']=ident
            st.success(f"Stored {f.name} with {len(segments)} readable section(s).")
            st.rerun()
        except ValueError as e: st.error(str(e))
    st.divider()
    st.markdown("### Uploaded sources")
    if not uploads:
        st.info("Upload your first playbook above, or start by adding a play manually in the library.")
    else:
        choices={u['id']:u['filename']+f" · #{u['id']}" for u in uploads}
        default=st.session_state.get('latest_upload')
        idx=list(choices).index(default) if default in choices else 0
        source_id=st.selectbox("Choose an uploaded source",list(choices),index=idx,format_func=lambda k:choices[k])
        doc=store.one("SELECT * FROM uploads WHERE id=? AND team_id=?",(source_id,team_id))
        segs=json.loads(doc['segments_json']); warns=json.loads(doc['warnings_json'])
        a,b=st.columns([4,1])
        a.caption(f"{doc['filename']} · {len(segs)} text sections · uploaded {doc['created_at']}")
        b.download_button("Original file",data=doc['filebytes'],file_name=doc['filename'],mime='application/octet-stream',use_container_width=True)
        if doc['filetype'] in ('png','jpg','jpeg'):
            st.image(doc['filebytes'],caption=doc['filename'],width=540)
        for w in warns: st.warning(w)
        st.markdown("### Create a play from this source")
        st.caption("You control the final play name, positions, and assignments. Extraction does not invent coaching instructions.")
        options=list(range(len(segs)))
        seg_idx=st.selectbox("Document section",options,format_func=lambda j:f"{segs[j]['source']}: {segs[j]['heading']}") if options else None
        seg=segs[seg_idx] if seg_idx is not None else {"heading":"","text":"","source":"Original attachment"}
        if seg_idx is not None:
            with st.expander("Review extracted text",expanded=True):
                st.text(seg['text'][:7000] or 'No text')
        # Key includes source and segment to ensure the form defaults refresh.
        with st.form(f"source_to_play_{source_id}_{seg_idx}"):
            a,b=st.columns(2)
            name=a.text_input("Play name",value=seg['heading'] if seg['heading'] and seg_idx is not None else '')
            unit=b.selectbox("Unit",UNITS)
            pos=st.multiselect("Assign to position groups",POSITIONS,default=[])
            a,b=st.columns(2)
            form=a.text_input("Formation / front")
            sit=b.text_input("Situation")
            assignment=st.text_area("Position responsibilities (coach-reviewed)",placeholder="Describe exactly what your players are expected to do.")
            coaching=st.text_area("Coaching points",placeholder="Teaching points, checks, adjustments...")
            if st.form_submit_button("Add to play library",type="primary"):
                if not name.strip() or not pos: st.error("Enter the play name and at least one position.")
                else:
                    store.write("""INSERT INTO plays(team_id,title,unit,positions,formation,situation,assignment,coaching_points,source_upload_id,source_segment)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",(team_id,name.strip(),unit,','.join(pos),form,sit,assignment,coaching,source_id,seg['source']))
                    st.success(f"'{name}' is now in the library.")
        with st.expander("Delete uploaded source"):
            st.caption("Deleting a source retains play cards but unlinks the attachment.")
            confirmed=st.checkbox("Permanently delete this file",key=f"source_confirm_{source_id}")
            if st.button("Delete source",disabled=not confirmed,key=f"delete_source_{source_id}"):
                store.write("DELETE FROM uploads WHERE id=? AND team_id=?",(source_id,team_id))
                st.session_state.pop('latest_upload',None)
                st.rerun()

elif section=="Weekly Installs":
    headline("Weekly Installs","Give the team a focused set of plays for the week—not the entire playbook.")
    with st.expander("＋ Create a weekly install",expanded=not bool(installs)):
        with st.form("new_install",clear_on_submit=True):
            a,b=st.columns(2)
            title=a.text_input("Install title",placeholder="Week 5 — Base Offense")
            opponent=b.text_input("Opponent",placeholder="Central Tigers")
            c,d=st.columns(2)
            week=c.text_input("Week / label",placeholder="Week 5")
            when=d.date_input("Install date",value=date.today())
            notes=st.text_area("This week's coaching emphasis")
            ids=st.multiselect("Select assigned plays",options=[p['id'] for p in plays],format_func=lambda p:next(a['title']+' · '+a['unit'] for a in plays if a['id']==p))
            if st.form_submit_button("Publish install",type="primary"):
                if not title.strip(): st.error("Give the install a title.")
                elif not ids: st.error("Select at least one play before publishing.")
                else:
                    store.create_install(team_id,title.strip(),opponent,week,when.isoformat(),notes,ids)
                    st.success("Install published in this prototype."); st.rerun()
    st.markdown("### Installs")
    if not installs: st.info("No installs published for this team yet.")
    for ins in installs:
        chosen=store.rows("""SELECT p.* FROM plays p JOIN install_plays ip ON p.id=ip.play_id
          WHERE ip.install_id=? AND p.team_id=? ORDER BY p.title""",(ins['id'],team_id))
        with st.expander(f"{ins['title']}  ·  {ins['install_date']}  ·  {len(chosen)} plays"):
            st.caption(f"Opponent: {ins['opponent'] or '—'} · {ins['week'] or 'No week'}")
            if ins['notes']: st.write(ins['notes'])
            if chosen:
                st.dataframe([{"Play":p['title'],"Unit":p['unit'],"Positions":full_positions(p['positions'])} for p in chosen],hide_index=True,use_container_width=True)
            with st.form(f"edit_inst_{ins['id']}"):
                selected_plays=st.multiselect("Adjust assigned plays",options=[p['id'] for p in plays],
                    default=[p['id'] for p in chosen],format_func=lambda p:next(a['title']+' · '+a['unit'] for a in plays if a['id']==p))
                if st.form_submit_button("Save assigned plays"):
                    store.update_install_plays(ins['id'],team_id,selected_plays)
                    st.success("Install updated."); st.rerun()
            if st.checkbox("Confirm deletion",key=f"confirm_inst_{ins['id']}"):
                if st.button("Delete install",key=f"delete_inst_{ins['id']}"):
                    store.write("DELETE FROM installs WHERE id=? AND team_id=?",(ins['id'],team_id))
                    st.rerun()

elif section=="Quiz Builder":
    headline("Quiz Builder", "Coaches write short checks for understanding for each play.")
    st.info("Questions are written and verified by the coach; answers are never automatically guessed from uploaded playbooks.")
    if not plays:
        st.info("Create a play in the library before adding quiz questions.")
    else:
        play_ids=[p['id'] for p in plays]
        chosen_id=st.selectbox("Choose a play",play_ids,
            format_func=lambda i:next(p['title']+' · '+p['unit'] for p in plays if p['id']==i),key="quiz_builder_play")
        questions=store.quiz_questions(team_id,chosen_id)
        st.caption(f"{len(questions)} question(s) for this play")
        with st.expander("＋ Add a question",expanded=not bool(questions)):
            with st.form(f"new_question_{team_id}_{chosen_id}",clear_on_submit=True):
                prompt=st.text_area("Question",placeholder="What is the first responsibility on this play?",max_chars=500)
                c1,c2=st.columns(2)
                answers=[c1.text_input("Answer A",max_chars=250),c2.text_input("Answer B",max_chars=250),
                         c1.text_input("Answer C",max_chars=250),c2.text_input("Answer D",max_chars=250)]
                correct=st.selectbox("Correct answer",["A","B","C","D"])
                if st.form_submit_button("Save question",type="primary"):
                    try:
                        store.add_quiz_question(team_id,chosen_id,prompt,answers,correct)
                        st.success("Question added.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        for index,q in enumerate(questions,1):
            with st.expander(f"Question {index} · {q['question_text']}"):
                for letter in ('A','B','C','D'):
                    st.write(f"{'✓ ' if letter==q['correct_option'] else ''}{letter}. {q['option_'+letter.lower()]}")
                if st.button("Delete question",key=f"delete_question_{team_id}_{q['id']}"):
                    store.delete_quiz_question(team_id,q['id'])
                    st.rerun()
        st.caption("Questions are available in Player Preview after this play is assigned to a weekly install.")

elif section=="Roster":
    headline("Roster","Define which players receive QB, OL, defensive, and special-teams assignments.")
    with st.expander("＋ Add a player",expanded=not bool(players)):
        with st.form("add_player",clear_on_submit=True):
            a,b,c=st.columns([2,1,1])
            name=a.text_input("Name")
            jersey=b.text_input("Jersey #")
            pos=c.selectbox("Position",[p for p in POSITIONS if p!="ALL"])
            if st.form_submit_button("Add to roster",type="primary"):
                if name.strip():
                    store.write("INSERT INTO players(team_id,name,jersey,position) VALUES(?,?,?,?)",(team_id,name.strip(),jersey.strip(),pos))
                    st.success("Player added."); st.rerun()
                else: st.error("Enter a player name.")
    st.markdown("### Import roster CSV")
    with st.expander("Import a roster from CSV"):
        st.caption("CSV header: name,jersey,position. Positions: QB, RB, WR, TE, OL, DL, LB, DB, ST.")
        csv_file=st.file_uploader("Roster .csv",type=["csv"],key="roster_csv")
        if csv_file and st.button("Import roster rows"):
            try:
                content=csv_file.getvalue().decode('utf-8-sig')
                if len(content)>500_000: raise ValueError("Roster CSV is too large")
                reader=csv.DictReader(StringIO(content))
                if not reader.fieldnames or not {'name','position'} <= {f.lower().strip() for f in reader.fieldnames}:
                    raise ValueError("CSV must have name and position columns (jersey is optional).")
                added=0; skipped=0
                for index,row in enumerate(reader):
                    if index>=300: skipped+=1; continue
                    clean={k.lower().strip(): (v or '').strip() for k,v in row.items() if k}
                    if clean.get('name') and clean.get('position','').upper() in POSITIONS and clean.get('position','').upper()!='ALL':
                        store.write("INSERT INTO players(team_id,name,jersey,position) VALUES (?,?,?,?)",
                                    (team_id,clean['name'],clean.get('jersey',''),clean['position'].upper()))
                        added+=1
                    else: skipped+=1
                st.success(f"Added {added} players; skipped {skipped} invalid/excess rows.")
                if added: st.rerun()
            except (UnicodeDecodeError,ValueError,csv.Error) as e: st.error(str(e))
    st.markdown(f"### Current roster ({len(players)})")
    if players:
        st.dataframe([{"Jersey":p['jersey'],"Player":p['name'],"Position":p['position']} for p in players],hide_index=True,use_container_width=True)
        with st.expander("Remove a player"):
            pid=st.selectbox("Choose player",[p['id'] for p in players],format_func=lambda i:next(p['name'] for p in players if p['id']==i))
            confirm=st.checkbox("I understand this will also remove the player's study progress.")
            if st.button("Remove player",disabled=not confirm):
                store.write("DELETE FROM players WHERE id=? AND team_id=?",(pid,team_id)); st.rerun()
    else: st.info("Add players to test position filtering and study statuses.")

elif section=="Player Preview":
    headline("Player Study Preview","See exactly what players would study, with position filtering and progress statuses.")
    st.warning("Coach-only preview — anyone with access to this app can select any player. Do not share this as a real player login or enter sensitive student information.",icon="🔒")
    if not players: st.info("Add a player to the roster first.")
    elif not installs: st.info("Publish a weekly install before previewing player study materials.")
    else:
        a,b=st.columns(2)
        player_id=a.selectbox("Preview player",[p['id'] for p in players],format_func=lambda i:next(p['name']+" · "+p['position'] for p in players if p['id']==i))
        install_id=b.selectbox("Install",[i['id'] for i in installs],format_func=lambda k:next(i['title'] for i in installs if i['id']==k))
        player=next(p for p in players if p['id']==player_id)
        visible=store.player_install_plays(team_id,player_id,install_id)
        ready=sum(1 for p in visible if p['study_status']=='Ready')
        total=len(visible)
        st.markdown(f"### {player['name']} · {player['position']}")
        a,b,c=st.columns(3)
        a.metric("Assigned plays",total)
        b.metric("Marked ready",ready)
        c.metric("Study progress",f"{(100*ready/total):.0f}%" if total else "—")
        if total: st.progress(ready/total)
        else: st.info("No assigned plays match this player's position. Add plays tagged with their position or ALL.")
        for p in visible:
            with st.expander(f"{p['title']} · {p['formation'] or p['unit']} · {p['study_status']}"):
                st.caption(p['unit']+" · "+full_positions(p['positions'])+" · "+(p['situation'] or 'General'))
                st.markdown("**Your responsibilities**")
                st.write(p['assignment'] or "Coach hasn't added your responsibilities yet.")
                st.markdown("**Coaching points**")
                st.write(p['coaching_points'] or "—")
                a,b=st.columns([2,1])
                choice=a.selectbox("Study status",["Not started","Studying","Ready"],
                   index=["Not started","Studying","Ready"].index(p['study_status']),key=f"status_{player_id}_{install_id}_{p['id']}")
                with b:
                    st.write("")
                    if st.button("Save status",key=f"save_{player_id}_{install_id}_{p['id']}"):
                        store.set_progress(team_id,player_id,install_id,p['id'],choice)
                        st.rerun()
                questions=store.quiz_questions(team_id,p['id'])
                if questions:
                    previous=store.last_quiz_attempt(team_id,player_id,install_id,p['id'])
                    if previous:
                        st.caption(f"Last quiz: {previous['correct_count']}/{previous['question_count']} correct ({100*previous['correct_count']//previous['question_count']}%)")
                    st.markdown("**Knowledge check**")
                    st.caption("Coach-written questions · demo only · results do not automatically change your study status.")
                    with st.form(f"quiz_form_{team_id}_{player_id}_{install_id}_{p['id']}"):
                        given={}
                        for num,q in enumerate(questions,1):
                            chosen=st.radio(f"{num}. {q['question_text']}",['A','B','C','D'],index=None,
                                format_func=lambda v,q=q:f"{v}. {q['option_'+v.lower()]}",
                                key=f"answer_{team_id}_{player_id}_{install_id}_{p['id']}_{q['id']}")
                            if chosen is not None:
                                given[q['id']]=chosen
                        submitted=st.form_submit_button("Submit knowledge check",type="primary")
                        if submitted:
                            try:
                                result=store.submit_quiz(team_id,player_id,install_id,p['id'],given)
                                st.success(f"Score: {result['correct']}/{result['total']} correct ({result['percent']}%).")
                            except ValueError as exc:
                                st.error(str(exc))

elif section=="Team Readiness":
    headline("Team Readiness", "See who has studied each week's plays and how their quiz attempts went.")
    st.warning("Demo reporting only: players have no secure accounts, and local results may be lost on a Streamlit restart.",icon="🔒")
    if not installs:
        st.info("Create a weekly install to see readiness results.")
    else:
        install_id=st.selectbox("Weekly install",[i['id'] for i in installs],
            format_func=lambda k:next(i['title'] for i in installs if i['id']==k),key="readiness_install")
        report=store.team_readiness(team_id,install_id)
        if report:
            count=sum(r['assigned'] for r in report)
            ready=sum(r['ready'] for r in report)
            scored=[r['average_quiz_score'] for r in report if r['average_quiz_score'] is not None]
            a,b,c=st.columns(3)
            a.metric("Assigned play studies",count)
            b.metric("Marked ready",f"{ready}/{count}" if count else "—")
            c.metric("Avg. player quiz score",f"{round(sum(scored)/len(scored))}%" if scored else "—")
            st.dataframe([{"Player":r['player'],"Position":r['position'],
                "Ready / Assigned":f"{r['ready']}/{r['assigned']}",
                "Quizzes attempted":r['quizzes_taken'],
                "Avg. latest score":f"{r['average_quiz_score']}%" if r['average_quiz_score'] is not None else "—"}
                for r in report],hide_index=True,use_container_width=True)
            st.caption("Readiness is self-marked; quiz scores are the player's most recent attempt per play. These are different measures.")
        else: st.info("There are no rostered players for this team.")

elif section=="Data & Settings":
    headline("Data & Settings","Prototype safeguards and backups.")
    st.subheader("Workspace details")
    st.write(f"**Team:** {team['name']}")
    st.write(f"**Season:** {team['season']}")
    st.write(f"**Code:** {team['code']}")
    st.caption("A workspace code is not an authentication mechanism. Do not treat it like a protected player or coach account.")
    st.markdown("### Back up this workspace")
    st.write("Export includes roster information, plays, study statuses, coach-written quizzes, quiz attempts, weekly installs, and original uploaded files.")
    st.download_button("Download complete JSON backup",data=store.export_team(team_id),
      file_name=f"friday-night-iq-team-{team_id}-backup.json",mime="application/json",type="primary")
    st.caption("Backups contain uploaded coaching files and player names. Store them securely. Restore/import is not implemented in this prototype.")
    st.markdown("### Before a real team launch")
    st.write("This is a local-first, single-coach development build. A production release needs secure coach/player login, controlled team membership, access audits, encrypted cloud file storage, and persistent hosted data. Streamlit Community Cloud's local filesystem is temporary, so do **not** use it as the only copy of important playbooks.")
    st.write("Scanned PDFs, hand-drawn diagrams, and image-only PowerPoint slides are retained but not automatically analyzed. Coaches author and verify assignments in this build.")