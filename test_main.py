from fastapi import FastAPI, params
from fastapi.testclient import TestClient
import sqlite3
import pytest
import json
import main
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
    sql_vals = (user['meeting_id'],)
    cursor = conn.execute(sql_findMeetingidQuery, sql_vals)
    sql_meetingid = cursor.fetchone ()
    
    sql_findUUIDQuery = "SELECT meeting_id FROM meetings WHERE meeting_id=?"
    cursor = conn.execute(sql_findUUIDQuery, (user['uid'],))
    sql_uuid = cursor.fetchone ()

    assert isMeetingIdValid(user["meeting_id"])
    assert str(user["meeting_id"]) == str(sql_meetingid)
    assert str(user["uid"]) == str(sql_uuid)