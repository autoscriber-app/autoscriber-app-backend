from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from basemodels import User, TranscriptEntry
from autoscriber import summarize
import uuid
import tempfile
import os
import random
import string
# Not needed for code, but dependencies needed for requirements
import aiofiles
import uvicorn


app = FastAPI()
origins = ["https://autoscriber.sagg.in:8000/"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DOMAIN = "http://autoscriber.sagg.in:8000"
# Get environ variables
USER = os.environ.get('SQL_USER')
PASSWORD = os.environ.get('SQL_PASS')
# Connect to mysql db
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
        CREATE TABLE IF NOT EXISTS `unprocessed` (
            `meeting_id` char(38) NOT NULL,
            `uid` char(38) NOT NULL,
            `name` varchar(255) NOT NULL,
            `dialogue` LONGTEXT NOT NULL,
            `time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (meeting_id, time)
        ) DEFAULT CHARSET = utf8;
    '''
    processed = '''
        CREATE TABLE IF NOT EXISTS `processed` (
            `meeting_id` char(38) NOT NULL,
            `notes` LONGTEXT NOT NULL,
            `download_link` TINYTEXT NOT NULL,
            date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (meeting_id)
        ) DEFAULT CHARSET = utf8;
    '''
    meetings = '''
        CREATE TABLE IF NOT EXISTS `meetings` (
            `meeting_id` char(38) NOT NULL,
            `host_uid` char(38) NOT NULL,
            PRIMARY KEY (meeting_id)
        ) DEFAULT CHARSET = utf8;
    '''
    for e in (unprocessed, processed, meetings):
        mycursor.execute(e)
    print("Tables are ready!")


sql_setup()


# Returns a random Uuid with the length of 10; makes sure that uuid isn't taken
def uuidCreator():
    randomUuid = ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=10))
    sql_check_uuid = "SELECT `meeting_id` FROM meetings WHERE meeting_id=\"%s\""
    sql_vals = (randomUuid,)
    mycursor.execute(sql_check_uuid, params=sql_vals)
    if (mycursor.fetchone() is not None):
        return uuidCreator()
    return randomUuid


# Client makes get request
# Server responds with User dict
@app.post("/host")
def host_meeting():
    user = {'meeting_id': str(uuidCreator()), 'uid': str(uuid.uuid4())}

    # Create meeting in meetings db
    sql_add_meeting = "INSERT INTO meetings (meeting_id, host_uid) VALUES (%s, %s)"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_add_meeting, params=sql_vals)
    db.commit()
    return user


# Client makes post request with a dictionary that has "meeting_id" & "name" key
# Server responds with User
@app.post("/join")
def join_meeting(user: User):
    user = user.dict()

    # Check if meeting exists
    sql_find_meeting = "SELECT * FROM meetings WHERE meeting_id = %s"
    sql_vals = (user['meeting_id'],)
    mycursor.execute(sql_find_meeting, params=sql_vals)

    if mycursor.fetchone() is None:
        return HTTPException(status_code=406, detail="Meeting does not exist")
    user["uid"] = str(uuid.uuid4())
    return user


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    user = transcript_entry.user

    # Check if meeting exists
    sql_find_meeting = "SELECT * FROM meetings WHERE meeting_id = %s"
    sql_vals = (user.meeting_id,)
    mycursor.execute(sql_find_meeting, params=sql_vals)
    if mycursor.fetchone() is None:
        return HTTPException(status_code=406, detail="Meeting does not exist")

    sql_add_dialogue = "INSERT INTO unprocessed (meeting_id, uid, name, dialogue) VALUES (%s, %s, %s, %s)"
    sql_vals = (user.meeting_id, user.uid,
                user.name, transcript_entry.dialogue)
    mycursor.execute(sql_add_dialogue, params=sql_vals)
    db.commit()


@app.post("/end")
def end_meeting(user: User):
    user = user.dict()

    # Check `meetings` table to confirm that user is meeting host
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = %s AND host_uid = %s"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_get_host, params=sql_vals)
    if mycursor.fetchone() is None:
        return HTTPException(status_code=403, detail="User must be meeting host to end meeting")

    # Get dialogue blobs from `unprocessed` table
    sql_get_dialogue = "SELECT dialogue FROM unprocessed WHERE meeting_id = %s ORDER BY time"
    sql_vals = (user['meeting_id'],)
    mycursor.execute(sql_get_dialogue, params=sql_vals)
    dialogue = mycursor.fetchall()

    # Now that meeting is ended, we can clean db of all dialogue from the meeting
    # Delete all rows from `unprocessed` & `meetings` where meeting_id = user's meeting_id
    sql_remove_meeting = ("DELETE FROM unprocessed WHERE meeting_id = %s",
                          "DELETE FROM meetings WHERE meeting_id = %s")
    sql_vals = (user['meeting_id'],)
    # Remove from `unprocessed`
    mycursor.execute(sql_remove_meeting[0], params=sql_vals)
    # Remove from `meetings`
    mycursor.execute(sql_remove_meeting[1], params=sql_vals)
    db.commit()

    # Format transcript for autoscriber.summarize()
    # Each line looks like this: "Name: dialogue" and all lines are joined with \n
    transcript = "\n".join([line[0] for line in dialogue])

    # Summarize notes using autoscriber.summarize()
    notes = summarize(transcript)
    notes = md_format(notes)

    # Generate download link
    download_link = f"{DOMAIN}/download?id={user['meeting_id']}"

    # Insert notes into processed table
    sql_insert_notes = "INSERT INTO processed (meeting_id, notes, download_link) VALUES (%s, %s, %s)"
    sql_vals = (user['meeting_id'], notes, download_link)
    mycursor.execute(sql_insert_notes, params=sql_vals)
    db.commit()

    return {"notes": notes, "download_link": download_link}


def md_format(notes):
    md = ""
    for line in notes:
        md += f"- {line}  \n"
    return md


@ app.get("/download")
def download_notes(id: str):
    # Query sql `processed` table from notes
    sql_get_processed = "SELECT notes, date FROM processed WHERE meeting_id = %s"
    sql_vals = (id,)
    mycursor.execute(sql_get_processed, params=sql_vals)
    res = mycursor.fetchone()
    if res is None:
        return HTTPException(status_code=406, detail="Meeting does not exist")
    notes, date = res

    # Create md file for file response
    md_file = tempfile.NamedTemporaryFile(delete=False, suffix='.md')
    fname = f'{date.date()}-notes.md'
    md_file.write(bytes(notes, encoding='utf-8'))
    return FileResponse(md_file.name, media_type="markdown", filename=fname)
