from fastapi import FastAPI, params
from fastapi.testclient import TestClient
import mysql
import pytest
import json
import main
client = TestClient(main.app)

USER = ""
PASSWORD = ""
db = mysql.connector.connect(
    host="localhost",
    user=USER,
    password=PASSWORD,
    database="testScriber"
)

mycursor = db.cursor()

def isMeetingIdValid(id):
    return len(id) == 10

def test_meetingId():
    newMeetingid = main.uuidCreator()
    assert isMeetingIdValid(newMeetingid)

def test_hostEndpoint () :
    response = client.get("/host")
    user = json.loads(response.json())

    sql_findMeetingidQuery = "SELECT meeting_id FROM meetings WHERE meeting_id=%s"
    mycursor.execute(sql_findMeetingidQuery, params= (user['meeting_id']))
    db.commit()
    sql_meetingid = mycursor.get_row()
    sql_findUUIDQuery = "SELECT meeting_id FROM meetings WHERE meeting_id=%s"
    mycursor.execute(sql_findUUIDQuery, params= (user['user_id']))
    db.commit()
    sql_uuid = mycursor.get_row()


    assert isMeetingIdValid(user["meeting_id"])
    assert response.json() == {
        "meeting_id" : str(sql_meetingid),
        "uid" : str(sql_uuid),
    }
    