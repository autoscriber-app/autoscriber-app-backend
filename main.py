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
                  "name varchar(255) NOT NULL, message LONGTEXT NOT NULL, time TIMESTAMP NOT NULL DEFAULT " \
                  "CURRENT_TIMESTAMP, PRIMARY KEY (meetingid, time)) DEFAULT CHARSET=utf8; "
    processed = "CREATE TABLE IF NOT EXISTS processed (meetingid char(38) NOT NULL, notes LONGTEXT NOT NULL, " \
                "date DATE NOT NULL, PRIMARY KEY (meetingid)) DEFAULT CHARSET=utf8; "
    meetings = "CREATE TABLE IF NOT EXISTS meetings (meetingid char(38) NOT NULL, host_uid char(38), PRIMARY KEY (" \
               "meetingid)) DEFAULT CHARSET=utf8; "
    for e in (unprocessed, processed, meetings):
        mycursor.execute(e)
    print("Tables are ready!")
create_tables()


# Client makes post request with a dictionary that has "user" key
# Server responds with User
@app.post("/start")
def start_meeting(user: User):
    user = user.dict()
    user['meetingid'] = uuid.uuid4()
    user['uid'] = uuid.uuid4()
    return user


# Client makes post request with a dictionary that has "meetingid" & "user" key
# Server responds with User
@app.post("/join")
def join_meeting(user: User):
    user = user.dict()
    user["uid"] = uuid.uuid4()
    return user


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    return transcript_entry


@app.post("/end")
def end_meeting(user: User):
    return user.dict()
