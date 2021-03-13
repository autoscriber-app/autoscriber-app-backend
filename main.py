from fastapi import FastAPI
import mysql.connector
from basemodels import User, TranscriptEntry
from autoscriber import summarize
import uuid
import markdown


app = FastAPI()
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=open("sql_pass").read(),
    database="autoscriber_app",
)
mycursor = db.cursor()
domain = "http://localhost:8000"


# Setting up sql - Creating Tables
def create_tables():
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
create_tables()


# Client makes post request with a dictionary that has "name" key
# Server responds with User
@app.post("/host")
def host_meeting(user: User):
    user = user.dict()
    user['meeting_id'], user['uid'] = str(uuid.uuid4()), str(uuid.uuid4())

    # Create meeting in meetings db
    sql_add_meeting = "INSERT INTO meetings (meeting_id, host_uid) VALUES (%s, %s)"
    vals = (user['meeting_id'], user['uid'])
    mycursor.execute(sql_add_meeting, params=vals)
    db.commit()

    return user


# Client makes post request with a dictionary that has "meeting_id" & "name" key
# Server responds with User
@app.post("/join")
def join_meeting(user: User):
    user = user.dict()

    # Check if meeting exists
    sql_find_meeting = "SELECT * FROM meetings WHERE meeting_id = '%s'" % user["meeting_id"]
    mycursor.execute(sql_find_meeting)

    if mycursor.fetchone() is not None:
        user["uid"] = str(uuid.uuid4())
        return user
    return "Meeting does not exist. Please check with host to ensure your invite link is correct."


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    user = transcript_entry.user

    sql_add_dialogue = "INSERT INTO unprocessed (meeting_id, uid, name, dialogue) VALUES (%s, %s, %s, %s)"
    vals = (user.meeting_id, user.uid, user.name, transcript_entry.dialogue)
    mycursor.execute(sql_add_dialogue, params=vals)
    db.commit()

    return 200


@app.post("/end")
def end_meeting(user: User):
    user = user.dict()

    # Check `meetings` table to confirm that user is meeting host
    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = '%s' AND host_uid = '%s'" % (
    user['meeting_id'], user['uid'])
    mycursor.execute(sql_get_host)
    if mycursor.fetchone() is None:
        return "Only host can end meeting."

    # Get dialogue blobs from `unprocessed` table
    sql_get_dialogue = "SELECT name, dialogue FROM unprocessed WHERE meeting_id = '%s' ORDER BY time" % user['meeting_id']
    mycursor.execute(sql_get_dialogue)
    dialogue = mycursor.fetchall()

    # Format transcript for autoscriber.summarize()
    # Each line looks like this: "Name: dialogue" and all lines are joined with \n
    transcript = "\n".join([": ".join(line) for line in dialogue])

    # Summarize notes using autoscriber.summarize()
    notes = summarize(transcript)

    # Generate download link
    download_link = domain + "/download?id={}".format(user['meeting_id'])

    # Insert notes into processed table
    sql_insert_notes = "INSERT INTO processed (meeting_id, notes, download_link) VALUES (%s, %s, %s)"
    vals = (user['meeting_id'], notes, download_link)
    mycursor.execute(sql_insert_notes, params=vals)
    db.commit()

    # Now that meeting is ended, we can clean db of all dialogue from the meeting
    # Delete all rows from `unprocessed` & `meetings` where meeting_id = user's meeting_id
    sql_remove_meeting = ("DELETE FROM unprocessed WHERE meeting_id = '%s' " % user['meeting_id'],
                          "DELETE FROM meetings WHERE meeting_id = '%s' " % user['meeting_id'])
    mycursor.execute(sql_remove_meeting[0])     # Remove from `unprocessed`
    mycursor.execute(sql_remove_meeting[1])     # Remove from `meetings`
    db.commit()

    return {"notes": notes, "download_link": download_link}


@app.get("/download")
def download_notes(id: str):
    # Query sql `processed` table from notes
    sql_get_processed = "SELECT notes FROM processed WHERE meeting_id = '%s'" % id
    mycursor.execute(sql_get_processed)
    notes = mycursor.fetchone()[0]
    notes = notes.split('\n')
    # notes = notes.replace("\n", "  ")   # MD uses double-space to signify new line
    md = ""
    for line in notes:
        md += markdown.markdown("- " + line)
    return md
