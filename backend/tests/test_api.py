import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.context import AppContext
from app.db import Database
from app.main import create_app
from app.pipeline.asr.mock import MockAsr
from app.pipeline.correction.rules import RulesCorrector
from app.pipeline.demo import write_demo_wav
from app.pipeline.orchestrator import Engines
from app.pipeline.pronunciation.mock import MockPronunciation


@pytest.fixture
def client(tmp_path):
    s = Settings(_env_file=None, data_dir=tmp_path / "data", worker_threads=1)
    ctx = AppContext(s, Database(":memory:"),
                     Engines(MockAsr(), RulesCorrector(), MockPronunciation()))
    with TestClient(create_app(s, ctx)) as c:
        yield c


@pytest.fixture
def wav_bytes(tmp_path):
    p = tmp_path / "x.wav"
    write_demo_wav(p)
    return p.read_bytes()


def upload(client, wav_bytes, **form):
    r = client.post("/api/recordings", files={"file": ("léa.wav", wav_bytes, "audio/wav")}, data=form)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    for _ in range(100):
        d = client.get(f"/api/recordings/{rid}").json()
        if d["status"] in {"done", "failed"}:
            return d
        time.sleep(0.1)
    raise AssertionError("job timeout")


def test_health(client):
    h = client.get("/api/health").json()
    assert h["engines"]["asr"] == "mock" and h["degraded"] is True


def test_upload_analyze_grade_flow(client, wav_bytes):
    d = upload(client, wav_bytes, title="Oral Léa", student_name="Léa")
    assert d["status"] == "done" and d["title"] == "Oral Léa"
    errs = d["analysis"]["errors"]
    assert {e["category"] for e in errs} == {"grammar", "conjugation", "vocabulary", "pronunciation"}
    before = d["grade"]["total"]
    rid = d["id"]
    # reject an error -> grade cannot decrease
    major = next(e for e in errs if e["severity"] == "major")
    r = client.patch(f"/api/recordings/{rid}/errors/{major['id']}", json={"status": "rejected"})
    assert r.status_code == 200 and r.json()["grade"]["total"] >= before
    # manual criterion changes the grade
    g1 = client.put(f"/api/recordings/{rid}/rubric", json={"manual": {"flu": 2}}).json()["grade"]
    assert g1["total"] > r.json()["grade"]["total"]
    assert client.get(f"/api/recordings/{rid}/grade").json()["total"] == g1["total"]


def test_list_has_grades_and_delete(client, wav_bytes):
    d = upload(client, wav_bytes)
    lst = client.get("/api/recordings").json()
    assert lst[0]["id"] == d["id"] and lst[0]["grade"]["out_of"] == 20
    assert client.delete(f"/api/recordings/{d['id']}").status_code == 204
    assert client.get(f"/api/recordings/{d['id']}").status_code == 404


def test_audio_range_and_peaks(client, wav_bytes):
    d = upload(client, wav_bytes)
    r = client.get(f"/api/recordings/{d['id']}/audio", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    p = client.get(f"/api/recordings/{d['id']}/peaks?bins=100").json()
    assert len(p["peaks"]) == 100 and p["duration"] > 30


def test_add_and_delete_manual_error(client, wav_bytes):
    d = upload(client, wav_bytes)
    rid = d["id"]
    r = client.post(f"/api/recordings/{rid}/errors", json={
        "category": "vocabulary", "start": 3.0, "end": 3.4, "heard": "x", "expected": "y",
        "severity": "major"})
    assert r.status_code == 201
    eid = r.json()["created"]
    assert next(e for e in r.json()["analysis"]["errors"] if e["id"] == eid)["status"] == "confirmed"
    assert client.delete(f"/api/recordings/{rid}/errors/{eid}").status_code == 200
    assert client.delete(f"/api/recordings/{rid}/errors/{eid}").status_code == 404


def test_regrade_segment_runs_checks(client, wav_bytes):
    d = upload(client, wav_bytes)
    rid = d["id"]
    segs = {s["id"]: s for s in d["analysis"]["segments"]}
    assert segs["s5"]["role"] == "teacher"
    # student segment (French) un-graded -> graded False; flipping a teacher segment keeps it harmless
    r = client.patch(f"/api/recordings/{rid}/segments/s3", json={"role": "teacher"})
    assert r.status_code == 200
    seg3 = next(s for s in r.json()["analysis"]["segments"] if s["id"] == "s3")
    assert seg3["graded"] is False
    g_before = r.json()["grade"]["total"]
    r = client.patch(f"/api/recordings/{rid}/segments/s3", json={"role": "student"})
    assert r.json()["grade"]["total"] <= g_before  # errors of s3 count again
    assert any(e["segment_id"] == "s3" for e in r.json()["analysis"]["errors"])


def test_rubric_crud_and_preview(client, wav_bytes):
    rubs = client.get("/api/rubrics").json()
    assert len(rubs) == 2  # standard + recitation presets
    new = {**rubs[0], "name": "Strict /10", "total_points": 10, "id": None}
    r = client.post("/api/rubrics", json=new)
    assert r.status_code == 201 and r.json()["id"] != rubs[0]["id"]
    d = upload(client, wav_bytes)
    pv = client.post("/api/grading/preview", json={"recording_id": d["id"], "rubric": new}).json()
    assert pv["out_of"] == 10
    bad = {**new, "criteria": [{**new["criteria"][0], "category": None}]}
    assert client.post("/api/rubrics", json=bad).status_code == 422
    assert client.delete(f"/api/rubrics/{r.json()['id']}").status_code == 204
    assert client.delete(f"/api/rubrics/{rubs[1]['id']}").status_code == 204
    assert client.delete(f"/api/rubrics/{rubs[0]['id']}").status_code == 409  # last one stays


def test_exports(client, wav_bytes):
    d = upload(client, wav_bytes)
    csv_ = client.get(f"/api/recordings/{d['id']}/export.csv")
    assert "timecode" in csv_.text and "NOTE" in csv_.text
    assert client.get(f"/api/recordings/{d['id']}/export.json").json()["analysis"]["errors"]


def test_bad_upload(client):
    r = client.post("/api/recordings", files={"file": ("empty.wav", b"", "audio/wav")})
    assert r.status_code == 400
    d = upload(client, b"not audio at all", title="bad")
    assert d["status"] == "failed" and d["error"]


def test_reference_text_flow(client, wav_bytes):
    d = upload(client, wav_bytes, reference_text="Hallo ich heiße Léa und ich wohne in Berlin")
    rid = d["id"]
    assert d["reference_text"].startswith("Hallo")
    assert d["analysis"]["engines"]["corrector"] == "texte de référence"
    assert all(e["source"] in ("reference", "phonemes", "asr_confidence")
               for e in d["analysis"]["errors"])
    assert any(e["category"] == "text" for e in d["analysis"]["errors"])
    recitation = next(r for r in client.get("/api/rubrics").json() if r["criteria"][0]["id"] == "text")
    g = client.put(f"/api/recordings/{rid}/rubric", json={"rubric_id": recitation["id"]}).json()["grade"]
    assert [c["id"] for c in g["criteria"]] == ["text", "pron", "rhythm"]
    rhythm = g["criteria"][2]
    assert rhythm["suggested"] is not None and rhythm["earned"] == rhythm["suggested"]
    g = client.put(f"/api/recordings/{rid}/rubric", json={"manual": {"rhythm": 0.5}}).json()["grade"]
    assert g["criteria"][2]["earned"] == 0.5
    g = client.put(f"/api/recordings/{rid}/rubric", json={"manual": {"rhythm": None}}).json()["grade"]
    assert g["criteria"][2]["earned"] == rhythm["suggested"]  # override removed
    # clearing the reference re-analyses with the grammar corrector
    assert client.put(f"/api/recordings/{rid}/reference", json={"text": ""}).status_code == 202
    for _ in range(100):
        d = client.get(f"/api/recordings/{rid}").json()
        if d["status"] == "done":
            break
        time.sleep(0.05)
    assert not any(e["category"] == "text" for e in d["analysis"]["errors"])


def test_existing_database_is_migrated(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    c = sqlite3.connect(path)
    c.executescript("""
      CREATE TABLE rubrics (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        json TEXT NOT NULL, created_at REAL NOT NULL);
      CREATE TABLE recordings (id TEXT PRIMARY KEY, title TEXT NOT NULL,
        student_name TEXT NOT NULL DEFAULT '', filename TEXT NOT NULL,
        audio_path TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'queued',
        stage TEXT NOT NULL DEFAULT 'queued', progress REAL NOT NULL DEFAULT 0,
        error TEXT NOT NULL DEFAULT '', duration REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL,
        rubric_id INTEGER, analysis_json TEXT, manual_json TEXT NOT NULL DEFAULT '{}');
      INSERT INTO recordings(id,title,filename,created_at) VALUES('a','t','f',0);
    """)
    c.commit()
    c.close()
    db = Database(path)
    assert db.get_recording("a")["reference_text"] == ""
    assert len(db.list_rubrics()) == 2
    db.close()
    assert len(Database(path).list_rubrics()) == 2  # the preset is added only once
