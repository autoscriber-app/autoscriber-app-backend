from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from autoscriber import summarize
from apscheduler.schedulers.background import BackgroundScheduler
from colorama import Fore
import uuid
import tempfile
import os
import random
import string

from basemodels import User, TranscriptEntry
from WSConnectionManager import ConnectionManager

# Not needed for code, but dependencies needed for requirements
import aiofiles
import uvicorn

# Set up FastAPI app
app = FastAPI(title="Autoscriber",
              description="Automatic online meeting notes with voice recognition and NLP.",
              version="0.0.1")
# origins = ["*"]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
DOMAIN = "https://autoscriber.sagg.in:8000"
# Get environ variables & connect to MySQL db
USER = os.environ.get('SQL_USER')
PASSWORD = os.environ.get('SQL_PASS')
db = mysql.connector.connect(
    host="localhost",
    user=USER,
    password=PASSWORD,
    database="autoscriber_app"
)
mycursor = db.cursor()
# WebSocket manager
manager = ConnectionManager()
# Task scheduler for cleaning processed table
scheduler = BackgroundScheduler(daemon=True)


@app.on_event('startup')
def startup_event():
    """FastAPI startup event. Setup SQL and start BackgroundScheduler"""
    sql_setup()
    print(Fore.GREEN + "PROCESS:\t" + Fore.MAGENTA + "SQL tables ready!")
    # Add job and start scheduler
    scheduler.add_job(sql_clean_processed, 'cron', day="*", hour="0")
    scheduler.start()
    print(Fore.GREEN + "PROCESS:\t" + Fore.MAGENTA +
          "BackgroundScheduler started!")


def sql_setup():
    """Setting up sql - Creating Tables"""
    unprocessed = '''
        CREATE TABLE IF NOT EXISTS `unprocessed` (
            `row_id` int NOT NULL AUTO_INCREMENT,
            `meeting_id` char(38) NOT NULL,
            `uid` char(38) NOT NULL,
            `name` varchar(255) NOT NULL,
            `dialogue` LONGTEXT NOT NULL,
            `time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (row_id)
        ) DEFAULT CHARSET = utf8;
    '''
    processed = '''
        CREATE TABLE IF NOT EXISTS `processed` (
            `meeting_id` char(38) NOT NULL,
            `notes` LONGTEXT NOT NULL,
            `notes_link` TINYTEXT NOT NULL,
            `transcript` LONGTEXT NOT NULL,
            `transcript_link` TINYTEXT NOT NULL,
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


@app.on_event('shutdown')
def shutdown_event():
    """FastAPI shutdown event"""
    scheduler.shutdown()
    print(Fore.GREEN + "PROCESS:\t" + Fore.MAGENTA +
          "BackgroundScheduler shutdown!")


def uuidCreator():
    """Returns a random Uuid with the length of 10; makes sure that uuid isn't taken"""
    randomUuid = ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=10))
    sql_check_uuid = "SELECT `meeting_id` FROM meetings WHERE meeting_id=\"%s\""
    sql_vals = (randomUuid,)
    mycursor.execute(sql_check_uuid, params=sql_vals)
    if (mycursor.fetchone() is not None):
        return uuidCreator()
    return randomUuid


def is_host(user: User):
    """Checks if user is host of a current meeting"""
    if isinstance(user, User):
        user = user.dict()
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = %s AND host_uid = %s"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_get_host, params=sql_vals)
    return mycursor.fetchone() is not None


@app.get("/version")
def get_version():
    """Returns the app version"""
    return app.version


# Checks if meeting id corresponds to a current meeting
@app.post("/is_valid_meeting")
def is_valid_meeting(meeting_id: str):
    """Checks if a given meeting_id is valid"""
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = %s"
    sql_vals = (meeting_id,)
    mycursor.execute(sql_get_host, params=sql_vals)
    return mycursor.fetchone() is not None


@app.websocket("/ws/{meeting_id}/{uid}")
async def connect_websocket(websocket: WebSocket, meeting_id: str, uid: str):
    """Websocket for all users to connect to"""
    user = User(meeting_id=meeting_id, uid=uid)
    await manager.connect(websocket, user)

    host_ws = False
    # If host WS, Check that user is host
    if is_host(user):
        host_ws = True

    # If user has joined late, send previous dialogue to user.
    join_meeting_event = {'event': 'join_meeting',
                          'previous_dialogue': get_meeting_dialogues(meeting_id)}
    if len(join_meeting_event['previous_dialogue']) >= 1:
        await websocket.send_json(join_meeting_event)

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect as e:
        manager.disconnect(websocket, user)
        if host_ws:
            await end_meeting(user)


@app.post("/host")
def host_meeting():
    """Hosts a meeting"""
    user = {'meeting_id': uuidCreator(), 'uid': str(uuid.uuid4())}

    # Create meeting in meetings db
    sql_add_meeting = "INSERT INTO meetings (meeting_id, host_uid) VALUES (%s, %s)"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_add_meeting, params=sql_vals)
    db.commit()
    return user


@app.post("/join")
def join_meeting(user: User):
    """Joins a specified meeting"""
    user = user.dict()

    # Check if meeting exists
    if not is_valid_meeting(meeting_id=user['meeting_id']):
        return HTTPException(status_code=406, detail="Meeting does not exist")

    user["uid"] = str(uuid.uuid4())
    return user


@app.post("/add")
async def add_to_transcript(transcript_entry: TranscriptEntry):
    """Adds a transcript entry to SQL"""

    user = transcript_entry.user

    # Check if meeting exists
    if not is_valid_meeting(meeting_id=user.meeting_id):
        return HTTPException(status_code=406, detail="Meeting does not exist")

    sql_add_dialogue = "INSERT INTO unprocessed (meeting_id, uid, name, dialogue) VALUES (%s, %s, %s, %s)"
    sql_vals = (user.meeting_id, user.uid,
                user.name, transcript_entry.dialogue)
    mycursor.execute(sql_add_dialogue, params=sql_vals)
    db.commit()

    res_json = {'event': 'transcript_entry',
                'name': user.name,
                'uid': user.uid,
                'message': transcript_entry.dialogue}
    # Broadcast event to all meeeting participants
    await manager.broadcast_meeting(res_json, meeting_id=user.meeting_id)


def get_meeting_dialogues(meeting_id: str):
    """Get dialogue blobs from `unprocessed` table"""
    sql_get_dialogue = "SELECT name, dialogue FROM unprocessed WHERE meeting_id = %s ORDER BY time"
    sql_vals = (meeting_id,)
    mycursor.execute(sql_get_dialogue, params=sql_vals)
    return mycursor.fetchall()


@app.post("/end")
async def end_meeting(user: User):
    """Ends a meeting - User must be host"""
    user = user.dict()

    # Check `meetings` table to confirm that user is meeting host
    if not is_host(user):
        return HTTPException(status_code=403, detail="User must be meeting host to end meeting")

    unprocessed = get_meeting_dialogues(user['meeting_id'])

    # Now that meeting is ended, we can clean db of all dialogue from the meeting
    # Delete all rows from `unprocessed` & `meetings` where meeting_id = user's meeting_id
    sql_remove_meeting(meeting_id=user['meeting_id'])
    # Broadcast that meeting is ended.
    await manager.broadcast_meeting({'event': 'end_meeting'}, meeting_id=user['meeting_id'])

    # Format transcript for autoscriber.summarize()
    transcript = []
    for line in unprocessed:
        name, dialogue = line[0], str(line[1].strip())
        if dialogue[-1] not in "!.,":
            dialogue += "."
        transcript.append(f"{name}: {dialogue}")
    transcript = " \n".join(transcript)

    # Summarize notes using autoscriber.summarize()
    notes = summarize(transcript)
    notes = format_notes(notes)

    # Generate download links
    notes_link, transcript_link = f"/notes?id={user['meeting_id']}", f"/transcript?id={user['meeting_id']}"

    # Insert notes, transcript into processed table
    sql_insert_notes = "INSERT INTO processed (meeting_id, notes, notes_link, transcript, transcript_link) VALUES (%s, %s, %s, %s, %s)"
    sql_vals = (user['meeting_id'], notes, notes_link,
                transcript, transcript_link)
    mycursor.execute(sql_insert_notes, params=sql_vals)
    db.commit()

    res_json = {"event": "done_processing",
                "notes_link": notes_link, "transcript_link": transcript_link}
    # Broadcast download link to all users in this meeting
    await manager.broadcast_meeting(res_json, meeting_id=user['meeting_id'])
    # Disconnect WS connection for all users in this meeting
    await manager.close_meeting(meeting_id=user['meeting_id'])
    return res_json


def sql_remove_meeting(meeting_id: str):
    """Removes a given meeting_id from `unprocessed` and `meetings` tables"""
    sql_remove_meeting = ("DELETE FROM unprocessed WHERE meeting_id = %s",
                          "DELETE FROM meetings WHERE meeting_id = %s")
    sql_vals = (meeting_id,)
    # Remove from `unprocessed`
    mycursor.execute(sql_remove_meeting[0], params=sql_vals)
    # Remove from `meetings`
    mycursor.execute(sql_remove_meeting[1], params=sql_vals)
    db.commit()


def format_notes(notes):
    """Simple function to convert format summarized notes in md"""
    md = ""
    for line in notes:
        md += f"- {line}  \n"
    return md


@app.get("/notes")
def download_notes(id: str):
    """Sends a file response to download summarized notes"""
    # Query sql `processed` table from notes
    sql_get_processed = "SELECT notes, date FROM processed WHERE meeting_id = %s"
    sql_vals = (id,)
    mycursor.execute(sql_get_processed, params=sql_vals)
    res = mycursor.fetchone()
    if res is None:
        return HTTPException(status_code=406, detail="Meeting does not exist. Meeting notes & transcripts are only stored for 30 days.")
    notes, date = res

    # Create md file for file response
    md_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    fname = f'{date.date()}_{id}_notes.txt'
    md_file.write(bytes(notes, encoding='utf-8'))
    return FileResponse(md_file.name, media_type="text", filename=fname)


@app.get("/transcript")
def download_transcript(id: str):
    """Sends a file response to download raw transcript"""
    # Query sql `processed` table from notes
    sql_get_processed = "SELECT transcript, date FROM processed WHERE meeting_id = %s"
    sql_vals = (id,)
    mycursor.execute(sql_get_processed, params=sql_vals)
    res = mycursor.fetchone()
    if res is None:
        return HTTPException(status_code=406, detail="Meeting does not exist. Meeting notes & transcripts are only stored for 30 days.")
    transcript, date = res

    # Create md file for file response
    md_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    fname = f'{date.date()}_{id}_transcript.txt'
    md_file.write(bytes(transcript, encoding='utf-8'))
    return FileResponse(md_file.name, media_type="text", filename=fname)


def sql_clean_processed():
    """Clean processed table to remove 30+ day old notes"""
    sql_clear_old = '''
    DELETE FROM `processed`
    WHERE DATE(date) < now() - interval 30 DAY
    '''
    mycursor.execute(sql_clear_old)
    db.commit()
    print(Fore.GREEN + "PROCESS:\t" + Fore.MAGENTA + "30+ day old notes cleaned!")
