from fastapi import FastAPI
import mysql.connector
import uuid
from basemodels import User, TranscriptEntry

app = FastAPI()
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=open("sql_pass").read(),
    database="autoscriber_app",
)
mycursor = db.cursor()


# Setting up sql - Creating Tables
def create_tables():
    unprocessed = "CREATE TABLE IF NOT EXISTS unprocessed (meetingid char(38) NOT NULL, uid char(38) NOT NULL, " \
                  "name varchar(255) NOT NULL, dialogue LONGTEXT NOT NULL, time TIMESTAMP NOT NULL DEFAULT " \
                  "CURRENT_TIMESTAMP, PRIMARY KEY (meetingid, time)) DEFAULT CHARSET=utf8; "
    processed = "CREATE TABLE IF NOT EXISTS processed (meetingid char(38) NOT NULL, notes LONGTEXT NOT NULL, " \
                "date DATE NOT NULL, PRIMARY KEY (meetingid)) DEFAULT CHARSET=utf8; "
    meetings = "CREATE TABLE IF NOT EXISTS meetings (meetingid char(38) NOT NULL, host_uid char(38) NOT NULL, PRIMARY KEY (" \
               "meetingid)) DEFAULT CHARSET=utf8; "
    for e in (unprocessed, processed, meetings):
        mycursor.execute(e)
    print("Tables are ready!")
create_tables()


# Client makes post request with a dictionary that has "name" key
# Server responds with User
@app.post("/host")
def host_meeting(user: User):
    user = user.dict()
    user['meetingid'], user['uid'] = str(uuid.uuid4()), str(uuid.uuid4())

    # Create meeting in meetings db
    sql = "INSERT INTO meetings (meetingid, host_uid) VALUES (%s, %s)"
    vals = (user['meetingid'], user['uid'])
    mycursor.execute(sql, vals)
    db.commit()

    return user


# Client makes post request with a dictionary that has "meetingid" & "name" key
# Server responds with User
@app.post("/join")
def join_meeting(user: User):
    user = user.dict()

    # Check if meeting exists
    sql = "SELECT * FROM meetings where meetingid = '%s'" % user["meetingid"]
    mycursor.execute(sql)

    if mycursor.fetchone() is not None:
        user["uid"] = str(uuid.uuid4())
        return user
    return "Meeting does not exist. Please check with host to ensure your invite link is correct."


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    user = transcript_entry.user
    sql = "INSERT INTO unprocessed (meetingid, uid, name, dialogue) VALUES (%s, %s, %s, %s)"
    vals = (user.meetingid, user.uid, user.name, transcript_entry.dialogue)

    mycursor.execute(sql, vals)
    db.commit()

    return transcript_entry


@app.post("/end")
def end_meeting(user: User):
    return user.dict()
