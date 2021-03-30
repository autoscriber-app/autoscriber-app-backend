from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import main

def test_meetingIDTest():
    newMeetingid = main.uuidCreator()
    assert len(newMeetingid) == 10