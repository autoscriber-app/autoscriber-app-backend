from fastapi import WebSocket
from basemodels import User
from collections import defaultdict
from typing import Dict, Optional


class ConnectionManager:
    def __init__(self):
        # Dictionary of all active meetings
        # The keys are the meeting_id, and the value is a dict
        # The inner dictionaries have similar structure to self.active_users, but only include users in the specified meeting_id
        self.meetings: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)

        # Dictionary of all active WebSockets
        # The keys are uid(user id) and the values are corresponding WebSocket
        self.active_users: Dict[str, WebSocket] = {}

    # Accepts a single websocket and adds to self.meetings and self.active_users
    async def connect(self, websocket: WebSocket, user: User):
        await websocket.accept()
        # Add user to meetings and active_users to keep track of them
        self.meetings[user.meeting_id][user.uid] = websocket
        self.active_users[user.uid] = websocket

    # Closes and removes a single websocket
    async def close(self, user: User, websocket: Optional[WebSocket] = None):
        if not websocket:
            websocket = self.active_users[user.uid]
        await websocket.close()

    async def close_meeting(self, meeting_id: str):
        for uid in self.meetings[meeting_id]:
            user = User(meeting_id=meeting_id, uid=uid)
            await self.close(user=user)
        self.meetings.pop()

    # Removes a single websocket from self.meetings and self.active_users
    def disconnect(self, websocket: WebSocket, user: User):
        # Remove from self.meetings if exists
        if user.meeting_id in self.meetings and \
                user.uid in self.meetings[user.meeting_id] and \
                self.meetings[user.meeting_id][user.uid] == websocket:
            self.meetings[user.meeting_id].pop(user.uid)

        # remove from self.active_users if exists
        if user.uid in self.active_users and self.active_users[user.uid] == websocket:
            self.active_users.pop(user.uid)

    # Send a message to a specific user
    # This method needs either the uid(user_id) or websocket of the user
    async def send_personal_message(self, message: str, websocket: WebSocket = None, uid: str = None):
        if websocket:
            await websocket.send_text(message)
        else:
            if uid in self.active_users:
                await self.active_users[uid].send_text(message)

    # Broadcast a message to all active users
    async def broadcast_active_users(self, message: str):
        for connection in self.active_users.values():
            await connection.send_text(message)

    # Broadcast a message to all active users in the given meeting
    async def broadcast_meeting(self, message: str, meeting_id: str):
        if meeting_id in self.meetings:
            for connection in self.meetings[meeting_id].values():
                await connection.send_text(message)
