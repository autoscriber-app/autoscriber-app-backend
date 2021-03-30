from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from basemodels import User, TranscriptEntry
# from autoscriber import summarize
import uuid
import tempfile
import os
import random
import string
# Not needed for code, but dependencies needed for requirements
import aiofiles
import uvicorn


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DOMAIN = "https://autoscriber.sagg.in:8000"
# Get environ variables
USER = os.environ.get('SQL_USER')
PASSWORD = os.environ.get('SQL_PASS')
db = mysql.connector.connect(
    host="localhost",
    user=USER,
    password=PASSWORD,
    database="autoscriber_app"
)
mycursor = db.cursor()


# Setting up sql - Creating Tables
def sql_setup():
    unprocessed = '''
        CREATE TABLE IF NOT EXISTS unprocessed (
            meeting_id char(38) NOT NULL,
            uid char(38) NOT NULL,
            name varchar(255) NOT NULL,
            dialogue LONGTEXT NOT NULL,
            time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (meeting_id, time)
        );
    '''
    processed = '''
        CREATE TABLE IF NOT EXISTS processed (
            meeting_id char(38) NOT NULL,
            notes LONGTEXT NOT NULL,
            download_link TINYTEXT NOT NULL,
            date DATETIME NOT NULL DEFAULT CURRENT_DATE,
            PRIMARY KEY (meeting_id)
        );
    '''
    meetings = '''
        CREATE TABLE IF NOT EXISTS meetings (
            meeting_id char(38) NOT NULL,
            host_uid char(38) NOT NULL,
            PRIMARY KEY (meeting_id)
        );
    '''
    for e in (unprocessed, processed, meetings):
        conn.execute(e)
    conn.commit()
    print("Tables are ready!")
sql_setup()


# Returns a random Uuid with the length of 10; makes sure that uuid isn't taken
def uuidCreator():
    randomUuid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    sql_check_uuid = "SELECT `meeting_id` FROM meetings WHERE meeting_id = ?"
    sql_vals = (randomUuid,)
    cursor = conn.execute(sql_check_uuid, sql_vals)
    if cursor.fetchone() is not None:
        return uuidCreator()
    return randomUuid


# Client makes get request
# Server responds with User dict
@app.get("/host")
def host_meeting():
    user = {'meeting_id': str(uuidCreator()), 'uid': str(uuid.uuid4())}

    # Create meeting in meetings db
    sql_add_meeting = "INSERT INTO meetings (meeting_id, host_uid) VALUES (?, ?)"
    sql_vals = (user['meeting_id'], user['uid'])
    conn.execute(sql_add_meeting, sql_vals)
    conn.commit()
    return user


# Client makes post request with a dictionary that has "meeting_id" & "name" key
# Server responds with User
@app.post("/join")
def join_meeting(user: User):
    user = user.dict()

    # Check if meeting exists
    sql_find_meeting = "SELECT * FROM meetings WHERE meeting_id = ?"
    sql_vals = (user['meeting_id'],)
    cursor = conn.execute(sql_find_meeting, sql_vals)

    if cursor.fetchone() is None:
        return HTTPException(status_code=406, detail="Meeting does not exist")
    user["uid"] = str(uuid.uuid4())
    return user


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    user = transcript_entry.user

    # Check if meeting exists
    sql_find_meeting = "SELECT * FROM meetings WHERE meeting_id = ?"
    sql_vals = (user.meeting_id,)
    cursor = conn.execute(sql_find_meeting, sql_vals)
    if cursor.fetchone() is None:
        return HTTPException(status_code=406, detail="Meeting does not exist")

    sql_add_dialogue = "INSERT INTO unprocessed (meeting_id, uid, name, dialogue) VALUES (?, ?, ?, ?)"
    sql_vals = (user.meeting_id, user.uid, user.name, transcript_entry.dialogue)
    conn.execute(sql_add_dialogue, sql_vals)
    conn.commit()


@app.post("/end")
def end_meeting(user: User):
    user = user.dict()

    # Check `meetings` table to confirm that user is meeting host
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = ? AND host_uid = ?"
    sql_vals = (user['meeting_id'], user['uid'])
    cursor = conn.execute(sql_get_host, sql_vals)
    if cursor.fetchone() is None:
        return HTTPException(status_code=403, detail="User must be meeting host to end meeting")

    # Get dialogue blobs from `unprocessed` table
    sql_get_dialogue = "SELECT name, dialogue FROM unprocessed WHERE meeting_id = ? ORDER BY time"
    sql_vals = (user['meeting_id'],)
    cursor = conn.execute(sql_get_dialogue, sql_vals)
    dialogue = cursor.fetchall()

    # Now that meeting is ended, we can clean db of all dialogue from the meeting
    # Delete all rows from `unprocessed` & `meetings` where meeting_id = user's meeting_id
    sql_remove_meeting = ("DELETE FROM unprocessed WHERE meeting_id = ?",
                          "DELETE FROM meetings WHERE meeting_id = ?")
    sql_vals = (user['meeting_id'],)
    conn.execute(sql_remove_meeting[0], sql_vals)    # Remove from `unprocessed`
    conn.execute(sql_remove_meeting[1], sql_vals)    # Remove from `meetings`
    conn.commit()

    # Format transcript for autoscriber.summarize()
    # Each line looks like this: "Name: dialogue" and all lines are joined with \n
    transcript = "\n".join([": ".join(line) for line in dialogue])

    # Summarize notes using autoscriber.summarize()
    # notes = summarize(transcript)
    notes = md_format(transcript)

    # Generate download link
    download_link = f"{DOMAIN}/download?id={user['meeting_id']}"

    # Insert notes into processed table
    sql_insert_notes = "INSERT INTO processed (meeting_id, notes, download_link) VALUES (?, ?, ?)"
    sql_vals = (user['meeting_id'], notes, download_link)
    conn.execute(sql_insert_notes, sql_vals)
    conn.commit()

    return {"notes": notes, "download_link": download_link}


def md_format(notes):
    md = ""
    for line in notes.split('\n'):
        md += f"- {line}  \n"
    return md


@app.get("/download")
def download_notes(id: str):
    # Query sql `processed` table from notes
    sql_get_processed = "SELECT notes, date FROM processed WHERE meeting_id = ?"
    sql_vals = (id,)
    cursor = conn.execute(sql_get_processed, sql_vals)
    res = cursor.fetchone()
    if res is None:
        return HTTPException(status_code=406, detail="Meeting does not exist")
    notes, date = res

    # Create md file for file response
    md_file = tempfile.NamedTemporaryFile(delete=False, suffix='.md')
    fname = f'{date}-notes.md'
    md_file.write(bytes(notes, encoding='utf-8'))
    return FileResponse(md_file.name, media_type="markdown", filename=fname)
