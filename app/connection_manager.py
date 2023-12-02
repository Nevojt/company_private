from datetime import datetime
import json
from fastapi import WebSocket
from app.database import async_session_maker
from app import models
from sqlalchemy import insert
from typing import Dict, Tuple







       # Connecting Private Messages     
class ConnectionManagerPrivate:
    def __init__(self):
        self.active_connections: Dict[Tuple[int, int], WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int, recipient_id: int):
        await websocket.accept()
        self.active_connections[(user_id, recipient_id)] = websocket

    def disconnect(self, user_id: int, recipient_id: int):
        self.active_connections.pop((user_id, recipient_id), None)

    async def send_private_message(self, message: str, sender_id: int, recipient_id: int, user_name: str, avatar: str, is_read: bool):
        sender_to_recipient = (sender_id, recipient_id)
        recipient_to_sender = (recipient_id, sender_id)
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_data = {
            "created_at": current_time,
            "sender_id": sender_id,
            "messages": message,
            "user_name": user_name,
            "avatar": avatar,
            "is_read": is_read
        }
        
        message_json = json.dumps(message_data, ensure_ascii=False)
        
        if sender_to_recipient in self.active_connections:
            await self.active_connections[sender_to_recipient].send_text(message_json)

        if recipient_to_sender in self.active_connections:
            await self.active_connections[recipient_to_sender].send_text(message_json)
        
        await self.add_private_message_to_database(message, sender_id, recipient_id)



            

    @staticmethod
    async def add_private_message_to_database(message: str, sender_id: int, recipient_id: int):
        async with async_session_maker() as session:
            stmt = insert(models.PrivateMessage).values(messages=message, sender_id=sender_id, recipient_id=recipient_id)
            await session.execute(stmt)
            await session.commit()
            # commit the changes to the database
            
class ConnectionManagerNotification:
    def __init__(self):
        self.active_connections: Dict[Tuple[int], WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active_connections.pop(user_id, None)