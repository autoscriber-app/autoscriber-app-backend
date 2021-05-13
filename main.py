from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from autoscriber import summarize

from basemodels import User, TranscriptEntry
from WSConnectionManager import ConnectionManager

import uuid
import tempfile
import os
import random
import string
# Not needed for code, but dependencies needed for requirements
import aiofiles
import uvicorn


app = FastAPI(title="Autoscriber App",
              description="Automatic online meeting notes with voice recognition and NLP.",
              version="0.0.1")
# origins = ["https://autoscriber-app.github.io"]
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DOMAIN = "https://autoscriber.sagg.in:8000"
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
manager = ConnectionManager()


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


# Checks if user is host of a current meeting
def is_host(user: User):
    if isinstance(user, User):
        user = user.dict()
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = %s AND host_uid = %s"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_get_host, params=sql_vals)
    return mycursor.fetchone() is not None

@app.get("/version")
def get_version():
    return app.version


# Checks if meeting id corresponds to a current meeting
@app.post("/is_valid_meeting")
def is_valid_meeting(meeting_id: str):
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = %s"
    sql_vals = (meeting_id,)
    mycursor.execute(sql_get_host, params=sql_vals)
    return mycursor.fetchone() is not None


# Client makes get request
# Server responds with User dict
@app.post("/host")
def host_meeting():
    user = {'meeting_id': uuidCreator(), 'uid': str(uuid.uuid4())}

    # Create meeting in meetings db
    sql_add_meeting = "INSERT INTO meetings (meeting_id, host_uid) VALUES (%s, %s)"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_add_meeting, params=sql_vals)
    db.commit()
    return user


# Websocket for host to connect to
@app.websocket("/ws/{meeting_id}/{uid}")
async def connect_websocket(websocket: WebSocket, meeting_id: str, uid: str):
    user = User(meeting_id=meeting_id, uid=uid)
    host_ws = False
    
    # If host WS, Check that user is host
    if is_host(user):
        host_ws = True
    await manager.connect(websocket, user)

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect as e:
        manager.disconnect(websocket, user)
        if host_ws:
            await end_meeting(user)


# Client makes post request with a dictionary that has "meeting_id" & "name" key
# Server responds with User
@app.post("/join")
def join_meeting(user: User):
    user = user.dict()

    # Check if meeting exists
    if not is_valid_meeting(meeting_id=user['meeting_id']):
        return HTTPException(status_code=406, detail="Meeting does not exist")

    user["uid"] = str(uuid.uuid4())
    return user


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    user = transcript_entry.user

    # Check if meeting exists
    if not is_valid_meeting(meeting_id=user.meeting_id):
        return HTTPException(status_code=406, detail="Meeting does not exist")

    sql_add_dialogue = "INSERT INTO unprocessed (meeting_id, uid, name, dialogue) VALUES (%s, %s, %s, %s)"
    sql_vals = (user.meeting_id, user.uid,
                user.name, transcript_entry.dialogue)
    mycursor.execute(sql_add_dialogue, params=sql_vals)
    db.commit()


@app.post("/end")
async def end_meeting(user: User):
    user = user.dict()

    # Check `meetings` table to confirm that user is meeting host
    if not is_host(user):
        return HTTPException(status_code=403, detail="User must be meeting host to end meeting")

    # Get dialogue blobs from `unprocessed` table
    sql_get_dialogue = "SELECT name, dialogue FROM unprocessed WHERE meeting_id = %s ORDER BY time"
    sql_vals = (user['meeting_id'],)
    mycursor.execute(sql_get_dialogue, params=sql_vals)
    unprocessed = mycursor.fetchall()

    # Now that meeting is ended, we can clean db of all dialogue from the meeting
    # Delete all rows from `unprocessed` & `meetings` where meeting_id = user's meeting_id
    remove_meeting(meeting_id=user['meeting_id'])
    # Broadcast that meeting is ended.
    await manager.broadcast_meeting(
        json={"event": "end_meeting"}, meeting_id=user['meeting_id'])

    # Format transcript for autoscriber.summarize()
    transcript = []
    for line in unprocessed:
        name, dialogue = line[0], line[1].strip()
        if dialogue[-1] not in "!.,":
            dialogue += "."
        transcript.append(f"{name}: {dialogue}")
    transcript = " \n".join(transcript)

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

    # Broadcast download link to all users in this meeting
    await manager.broadcast_meeting(json={"event": "done_processing", "download_link": download_link},
                              meeting_id=user['meeting_id'])
    # Disconnect WS connection for all users in this meeting
    await manager.close_meeting(meeting_id=user['meeting_id'])

    return {"notes": notes, "download_link": download_link}


# Removes a given meeting_id from `unprocessed` and `meetings` tables
def remove_meeting(meeting_id: str):
    sql_remove_meeting = ("DELETE FROM unprocessed WHERE meeting_id = %s",
                          "DELETE FROM meetings WHERE meeting_id = %s")
    sql_vals = (meeting_id,)
    # Remove from `unprocessed`
    mycursor.execute(sql_remove_meeting[0], params=sql_vals)
    # Remove from `meetings`
    mycursor.execute(sql_remove_meeting[1], params=sql_vals)
    db.commit()


def md_format(notes):
    md = ""
    for line in notes:
        md += f"- {line}  \n"
    return md


@app.get("/download")
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
