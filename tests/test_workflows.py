import base64
from io import BytesIO
import json
import pytest

import storage as s
from importers import extract

@pytest.fixture
def fresh_db(tmp_path,monkeypatch):
    monkeypatch.setenv('FRIDAY_NIGHT_IQ_DB',str(tmp_path/'test.sqlite'))
    s.init_db()
    return s.rows('SELECT * FROM teams')[0]['id']


def test_demo_team_starts_with_usable_play_cards(fresh_db):
    assert len(s.rows('SELECT * FROM plays WHERE team_id=?',(fresh_db,)))==3
    assert len(s.rows('SELECT * FROM players WHERE team_id=?',(fresh_db,)))==4


def test_position_filter_and_study_progress(fresh_db):
    team=fresh_db
    qb=s.one("SELECT id FROM players WHERE team_id=? AND position='QB'",(team,))['id']
    ol=s.one("SELECT id FROM players WHERE team_id=? AND position='OL'",(team,))['id']
    all_plays=s.rows('SELECT * FROM plays WHERE team_id=?',(team,))
    install=s.create_install(team,'Base','Test Opponent','Week 1','2027-09-01','', [p['id'] for p in all_plays])
    qb_visible=s.player_install_plays(team,qb,install)
    ol_visible=s.player_install_plays(team,ol,install)
    assert len(qb_visible)==2
    assert len(ol_visible)==1
    target=next(p['id'] for p in qb_visible if p['title']=='Mesh Concept')
    s.set_progress(team,qb,install,target,'Ready')
    status={p['id']:p['study_status'] for p in s.player_install_plays(team,qb,install)}
    assert status[target]=='Ready'
    with pytest.raises(ValueError):
        s.set_progress(team,ol,install,target,'Ready')


def test_team_isolation(fresh_db):
    second=s.create_team('Rival','2027')
    team=fresh_db
    foreign_play=s.rows('SELECT id FROM plays WHERE team_id=?',(team,))[0]['id']
    pid=s.write("INSERT INTO players(team_id,name,position) VALUES (?,?,?)",(second,'Second Team Player','QB'))
    install=s.create_install(second,'First','Other','1','2027-08-01','',[foreign_play])
    assert s.rows('SELECT * FROM install_plays WHERE install_id=?',(install,))==[]
    assert s.player_install_plays(second,pid,install)==[]
    with pytest.raises(ValueError):
        s.set_progress(second,pid,install,foreign_play,'Ready')


def test_export_includes_complete_data(fresh_db):
    doc=s.write("INSERT INTO uploads(team_id,filename,filetype,filebytes,segments_json,warnings_json) VALUES(?,?,?,?,?,?)",
                (fresh_db,'clip.png','png',b'\x89PNGsample','[]','[]'))
    data=json.loads(s.export_team(fresh_db))
    assert data['format']=='friday-night-iq-backup-v1'
    assert data['uploads'][0]['id']==doc
    assert base64.b64decode(data['uploads'][0]['filebytes'])==b'\x89PNGsample'


def test_text_and_csv_extraction():
    segments,warnings=extract('offense.txt',b'Outside zone\nBlock right\n---\nCounter GT\nPull left')
    assert len(segments)==2
    assert segments[1]['heading']=='Counter GT'
    assert not warnings
    rows,_=extract('plays.csv',b'name,assignment\nMesh,Run shallow cross\nZone,Block play side\n')
    assert len(rows)==2


def test_image_keeps_attachment_without_fabricated_text():
    parts,warnings=extract('play.png',b'fake-image-for-upload-test')
    assert parts==[]
    assert 'Image stored' in warnings[0]
    with pytest.raises(ValueError): extract('virus.exe',b'x')
    with pytest.raises(ValueError): extract('blank.pdf',b'')


def test_docx_extraction():
    from docx import Document
    doc=Document();doc.add_heading('Inside Zone',level=1);doc.add_paragraph('Covered step, vertical displacement')
    doc.add_heading('Power',level=1);doc.add_paragraph('Pull the backside guard')
    b=BytesIO();doc.save(b)
    parts,_=extract('playbook.docx',b.getvalue())
    assert len(parts)==2
    assert parts[1]['heading']=='Power'


def test_pptx_extraction():
    from pptx import Presentation
    p=Presentation(); slide=p.slides.add_slide(p.slide_layouts[1]);slide.shapes.title.text='Trips Mesh'
    b=BytesIO();p.save(b)
    parts,_=extract('playbook.pptx',b.getvalue())
    assert len(parts)==1
    assert parts[0]['heading']=='Trips Mesh'


def test_quiz_authoring_and_grade(fresh_db):
    team=fresh_db
    qb=s.one("SELECT id FROM players WHERE team_id=? AND position='QB'",(team,))['id']
    play=s.one("SELECT id FROM plays WHERE team_id=? AND title='Mesh Concept'",(team,))['id']
    ins=s.create_install(team,'Pass installs','Rival','2','2027-09-02','',[play])
    q=s.add_quiz_question(team,play,'Who reads the coverage?',
        ['Quarterback','Center','Punter','Safety'],'A')
    assert len(s.quiz_questions(team,play))==1
    with pytest.raises(ValueError,match='Answer every'):
        s.submit_quiz(team,qb,ins,play,{})
    a=s.submit_quiz(team,qb,ins,play,{q:'B'})
    assert a=={'correct':0,'total':1,'percent':0}
    a=s.submit_quiz(team,qb,ins,play,{q:'A'})
    assert a=={'correct':1,'total':1,'percent':100}
    assert s.last_quiz_attempt(team,qb,ins,play)['correct_count']==1
    assert len(s.rows('SELECT * FROM quiz_attempts WHERE team_id=?',(team,)))==2
    r=next(x for x in s.team_readiness(team,ins) if x['position']=='QB')
    assert r['assigned']==1 and r['quizzes_taken']==1 and r['average_quiz_score']==100
    assert r['ready']==0  # Grading does not impersonate a student's status.


def test_quiz_team_and_position_isolation(fresh_db):
    team=fresh_db
    second=s.create_team('Visitors','2027')
    qb=s.one("SELECT id FROM players WHERE team_id=? AND position='QB'",(team,))['id']
    lineman=s.one("SELECT id FROM players WHERE team_id=? AND position='OL'",(team,))['id']
    play=s.one("SELECT id FROM plays WHERE team_id=? AND title='Mesh Concept'",(team,))['id']
    inst=s.create_install(team,'Pass installs','Rival','2','2027-09-02','',[play])
    question=s.add_quiz_question(team,play,'Who reads the coverage?',
        ['Quarterback','Center','Punter','Safety'],'A')
    with pytest.raises(ValueError,match='not assigned'):
        s.submit_quiz(team,lineman,inst,play,{question:'A'})
    with pytest.raises(ValueError,match='not assigned'):
        s.submit_quiz(second,qb,inst,play,{question:'A'})
    with pytest.raises(ValueError,match='does not belong'):
        s.add_quiz_question(second,play,'Question',['A','B','C','D'],'A')
    assert s.quiz_questions(second,play)==[]
    assert s.team_readiness(second,inst)==[]
    s.delete_quiz_question(second,question)
    assert len(s.quiz_questions(team,play))==1
    assert s.last_quiz_attempt(second,qb,inst,play) is None


def test_quiz_rejects_invalid_questions_and_answers(fresh_db):
    team=fresh_db
    play=s.one('SELECT id FROM plays WHERE team_id=?',(team,))['id']
    for choices in (['One','one','Three','Four'],['A','B','C',''],['A','B','C']):
        with pytest.raises(ValueError):
            s.add_quiz_question(team,play,'Valid question?',choices,'A')
    with pytest.raises(ValueError):
        s.add_quiz_question(team,play,'Valid question?', ['A','B','C','D'],'E')
    q=s.add_quiz_question(team,play,'Valid question?', ['A','B','C','D'],'C')
    qb=s.one("SELECT id FROM players WHERE team_id=? AND position='QB'",(team,))['id']
    ins=s.create_install(team,'Install','Rival','1','2027-09-03','',[play])
    with pytest.raises(ValueError):
        s.submit_quiz(team,qb,ins,play,{q:'A',999:'C'})
    with pytest.raises(ValueError):
        s.submit_quiz(team,qb,ins,play,{q:'E'})
    s.delete_quiz_question(team,q)
    assert s.quiz_questions(team,play)==[]


def test_quiz_backup_includes_questions_and_attempts(fresh_db):
    team=fresh_db
    player=s.one("SELECT id FROM players WHERE team_id=? AND position='QB'",(team,))['id']
    play=s.one("SELECT id FROM plays WHERE team_id=? AND title='Mesh Concept'",(team,))['id']
    ins=s.create_install(team,'Install','Rival','1','2027-09-03','',[play])
    q=s.add_quiz_question(team,play,'Who throws?',['QB','RB','OL','DL'],'A')
    s.submit_quiz(team,player,ins,play,{q:'A'})
    data=json.loads(s.export_team(team))
    assert data['quiz_questions'][0]['question_text']=='Who throws?'
    assert data['quiz_attempts'][0]['correct_count']==1


def test_quiz_database_migration_is_idempotent(fresh_db):
    s.init_db()
    s.init_db()
    assert len(s.rows('SELECT * FROM teams WHERE id=?',(fresh_db,)))==1
    assert s.rows('SELECT * FROM quiz_questions')==[]