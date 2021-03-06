from pydantic import BaseModel


class User(BaseModel):
    meetingid: str = ''
    uid: str = ''
    name: str = ''


class TranscriptEntry(BaseModel):
    user: User
    dialogue: str