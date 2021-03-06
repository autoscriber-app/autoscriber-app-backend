from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
import uuid

app = FastAPI()


class TranscriptEntry(BaseModel):
    meetingid: str
    uuid: str
    name: str
    dialogue: str
    timestamp: int


class User(BaseModel):
    meetingid: str
    uuid: str


@app.get("/")
def root():
    return {'key': 'value'}


@app.post("/start")
def start_meeting(meet: str):
    uid = uuid.uuid4()
    return uid


@app.post("/join")
def join_meeting(meet: str):
    uid = uuid.uuid4()
    return uid


@app.post("/add")
def add_to_transcript(transcript_entry: TranscriptEntry):
    return transcript_entry


@app.post("/end")
def end_meeting(user: User):
    return user.dict()