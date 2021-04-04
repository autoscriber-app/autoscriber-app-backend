from fastapi import FastAPI, params
from fastapi.testclient import TestClient
import sqlite3
from pydantic.types import UUID4
import pytest
import json
from basemodels import User, TranscriptEntry
from requests.models import Response
import main
import uuid
client = TestClient(main.app)
conn = sqlite3.connect('autoscriber.db', check_same_thread=False)


def isMeetingIdValid(id):
    return len(id) == 10

def test_meetingId():
    newMeetingid = main.uuidCreator()
    assert isMeetingIdValid(newMeetingid)

def test_hostEndpoint () :
    response = client.post("/host")
    user = json.loads(str (response.text) )

    sql_findMeetingidQuery = "SELECT meeting_id FROM meetings WHERE meeting_id=?"
    sql_meetingid = conn.execute(sql_findMeetingidQuery, (user['meeting_id'],)).fetchone()
    assert isMeetingIdValid(user["meeting_id"])
    assert user["meeting_id"] == sql_meetingid[0]
    assert len(sql_meetingid) == 1


    sql_findUUIDQuery = "SELECT host_uid FROM meetings WHERE host_uid=?"
    sql_uuid = conn.execute(sql_findUUIDQuery, (user['uid'],)).fetchone()
    assert uuid.UUID(user["uid"])
    assert user["uid"] == sql_uuid[0]
    assert len(sql_uuid) == 1

def test_joinEndpoint () :
    hostResponse = client.post("/host")
    host = json.loads(str(hostResponse.text))
    userResponse = client.post(
        "/join",
        json= {
            "name" : "TEST USER",
            "meeting_id" : host["meeting_id"],
        })
    user = json.loads(str(userResponse.text))
    assert uuid.UUID(user["uid"])

def test_addEndpoint() :
    hostResponse = client.post("/host")
    host = json.loads(str(hostResponse.text))
    hostUser = User(meeting_id = host["meeting_id"], uid = host["uid"], name = "TEST HOST")
    transcript_entry = TranscriptEntry(user=hostUser, dialogue="TEST DIALOUGE")
    
    transcript_entryJSON = transcript_entry.json()
    hostResponse = client.post("/add", json=transcript_entryJSON)
    assert hostResponse.status_code == 200
    
    sql_addQuery = "SELECT uid, name, dialogue FROM unprocessed WHERE meeting_id = ?"
    sql_add = conn.execute(sql_addQuery, (hostUser.meeting_id,)).fetchone()

    assert transcript_entry.user.uid == sql_add[0]
    assert transcript_entry.user.name == sql_add[1]
    assert transcript_entry.dialogue == sql_add[2]
