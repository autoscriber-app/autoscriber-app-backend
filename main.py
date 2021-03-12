from fastapi import FastAPI
import mysql.connector
import uuid
from basemodels import User, TranscriptEntry
from autoscriber import summarize


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
    unprocessed = "CREATE TABLE IF NOT EXISTS unprocessed (meeting_id char(38) NOT NULL, uid char(38) NOT NULL, " \
                  "name varchar(255) NOT NULL, dialogue LONGTEXT NOT NULL, time TIMESTAMP NOT NULL DEFAULT " \
                  "CURRENT_TIMESTAMP, PRIMARY KEY (meeting_id, time)) DEFAULT CHARSET=utf8;"
    processed = "CREATE TABLE IF NOT EXISTS processed (meeting_id char(38) NOT NULL, notes LONGTEXT NOT NULL, " \
                "date DATE NOT NULL DEFAULT (DATE(CURRENT_TIMESTAMP)), PRIMARY KEY (meeting_id)) DEFAULT CHARSET=utf8; "
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

    sql_get_host = "SELECT * FROM meetings WHERE meeting_id = '%s' AND host_uid = '%s'" % (user['meeting_id'], user['uid'])
    mycursor.execute(sql_get_host)

    if mycursor.fetchone() is None:
        return "Only host can end meeting."

    sql_get_dialogue = "SELECT * FROM unprocessed WHERE meeting_id = '%s' ORDER BY time" % user['meeting_id']
    mycursor.execute(sql_get_dialogue)
    dialogue = mycursor.fetchall()

    sql_get_col_names = "SELECT Column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = N'unprocessed'"
    mycursor.execute(sql_get_col_names)
    col_names = mycursor.fetchall()

    transcript = []
    for line in dialogue:
        transcript.append({col_names[i][0]: line[i] for i in range(1, len(line))})
    
    # 
    # Do summarization
    # 
    summarized = "summarized"

    sql_insert_summarized = "INSERT INTO processed (meeting_id, notes) VALUES (%s, %s)"
    vals = (user['meeting_id'], summarized)
    mycursor.execute(sql_insert_summarized, params=vals)
    db.commit()

    return summarized
