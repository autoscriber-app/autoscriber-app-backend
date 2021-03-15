from fastapi import FastAPI
from fastapi.responses import FileResponse
import mysql.connector
from basemodels import User, TranscriptEntry
from autoscriber import summarize
from decouple import config
import uuid
import tempfile

# Not needed for code, but needed for requirements
import aiofiles
import uvicorn


app = FastAPI()
user, pswd = open("sql_setup").read().split('\n')
db = mysql.connector.connect(
    host="localhost",
    user=user,
    password=pswd,
    database="autoscriber_app"
)
mycursor = db.cursor()
# Get environ variables
DOMAIN = config('DOMAIN')


# Setting up sql - Creating Tables
def sql_setup():
    unprocessed = "CREATE TABLE IF NOT EXISTS unprocessed (meeting_id char(38) NOT NULL, uid char(38) NOT NULL, " \
                  "name varchar(255) NOT NULL, dialogue LONGTEXT NOT NULL, time TIMESTAMP NOT NULL DEFAULT " \
                  "CURRENT_TIMESTAMP, PRIMARY KEY (meeting_id, time)) DEFAULT CHARSET=utf8;"
    processed = "CREATE TABLE IF NOT EXISTS processed (meeting_id char(38) NOT NULL, notes LONGTEXT NOT NULL, " \
                "download_link TINYTEXT NOT NULL, date DATE NOT NULL DEFAULT (DATE(CURRENT_TIMESTAMP)), PRIMARY KEY (" \
                "meeting_id)) DEFAULT CHARSET=utf8;"
    meetings = "CREATE TABLE IF NOT EXISTS meetings (meeting_id char(38) NOT NULL, host_uid char(38) NOT NULL, " \
               "PRIMARY KEY (meeting_id)) DEFAULT CHARSET=utf8;"
    for e in (unprocessed, processed, meetings):
        mycursor.execute(e)
    print("Tables are ready!")
sql_setup()


# Client makes post request with a dictionary that has "name" key
# Server responds with User
@app.post("/host")
def host_meeting(user: User):
    user = user.dict()
    user['meeting_id'], user['uid'] = str(uuid.uuid4()), str(uuid.uuid4())

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

    if mycursor.fetchone() is not None:
        user["uid"] = str(uuid.uuid4())
        return user
    return "Meeting does not exist. Please check with host to ensure your invite link is correct."


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    user = transcript_entry.user

    sql_add_dialogue = "INSERT INTO unprocessed (meeting_id, uid, name, dialogue) VALUES (%s, %s, %s, %s)"
    sql_vals = (user.meeting_id, user.uid, user.name, transcript_entry.dialogue)
    mycursor.execute(sql_add_dialogue, params=sql_vals)
    db.commit()

    return 200


@app.post("/end")
def end_meeting(user: User):
    user = user.dict()

    # Check `meetings` table to confirm that user is meeting host
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = %s AND host_uid = %s"
    sql_vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_get_host, params=sql_vals)
    if mycursor.fetchone() is None:
        return "Only host can end meeting."

    # Get dialogue blobs from `unprocessed` table
    sql_get_dialogue = "SELECT name, dialogue FROM unprocessed WHERE meeting_id = %s ORDER BY time"
    sql_vals = (user['meeting_id'],)
    mycursor.execute(sql_get_dialogue, params=sql_vals)
    dialogue = mycursor.fetchall()

    # Format transcript for autoscriber.summarize()
    # Each line looks like this: "Name: dialogue" and all lines are joined with \n
    transcript = "\n".join([": ".join(line) for line in dialogue])

    # Summarize notes using autoscriber.summarize()
    notes = summarize(transcript)

    # Generate download link
    download_link = f"{DOMAIN}/download?id={user['meeting_id']}"

    # Insert notes into processed table
    sql_insert_notes = "INSERT INTO processed (meeting_id, notes, download_link) VALUES (%s, %s, %s)"
    sql_vals = (user['meeting_id'], notes, download_link)
    mycursor.execute(sql_insert_notes, params=sql_vals)
    db.commit()

    # Now that meeting is ended, we can clean db of all dialogue from the meeting
    # Delete all rows from `unprocessed` & `meetings` where meeting_id = user's meeting_id
    sql_remove_meeting = ("DELETE FROM unprocessed WHERE meeting_id = %s",
                          "DELETE FROM meetings WHERE meeting_id = %s")
    sql_vals = (user['meeting_id'],)
    mycursor.execute(sql_remove_meeting[0], params=sql_vals)    # Remove from `unprocessed`
    mycursor.execute(sql_remove_meeting[1], params=sql_vals)    # Remove from `meetings`
    db.commit()

    return {"notes": notes, "download_link": download_link}


@app.get("/download")
def download_notes(id: str):
    # Query sql `processed` table from notes
    sql_get_processed = "SELECT notes, date FROM processed WHERE meeting_id = %s"
    sql_vals = (id,)
    mycursor.execute(sql_get_processed, params=sql_vals)
    notes, date = mycursor.fetchone()
    notes = notes.split('\n')

    md_file = tempfile.NamedTemporaryFile(delete=False, suffix='.md')
    fname = f'{date}-notes.md'
    for line in notes:
        md_file.write(bytes("- " + line + "  \n", encoding='utf-8'))
    return FileResponse(md_file.name, media_type="markdown", filename=fname)
