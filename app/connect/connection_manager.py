from datetime import datetime
import pytz
import logging
from fastapi import WebSocket
from app.database.database import async_session_maker
from app.models import models
from app.schemas import schemas
from sqlalchemy import insert, update
from typing import Dict, Optional, Tuple
from app.security.crypto_messages import async_encrypt
from app.functions.fcm_sent_message import send_notifications_to_user
from sqlalchemy.ext.asyncio import AsyncSession


# Налаштування логування
logging.basicConfig(filename='_log/connect_manager.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)




       # Connecting Private Messages     
class ConnectionManagerPrivate:
    def __init__(self):
        self.active_connections: Dict[Tuple[int, int], WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int, recipient_id: int):
        await websocket.accept()
        self.active_connections[(user_id, recipient_id)] = websocket

    async def disconnect(self, user_id: int, recipient_id: int):
        self.active_connections.pop((user_id, recipient_id), None)

        
    async def send_private_all(self, message: Optional[str], file: Optional[str],
                               sender_id: int, receiver_id: int,
                               user_name: str, verified: bool,
                               avatar: str, id_return: Optional[int],
                               is_read: bool):
        
        sender_to_recipient = (sender_id, receiver_id)
        recipient_to_sender = (receiver_id, sender_id)
        
        timezone = pytz.timezone('UTC')
        current_time_utc = datetime.now(timezone)
        try:
            message_id = await self.add_private_all_to_database(sender_id, receiver_id, message, file, id_return, is_read)
            await self.mark_as_sent_message(message_id)
            # SocketModel
            socket_message = schemas.SocketModel(
                created_at=current_time_utc,
                id=message_id,
                receiver_id=sender_id,
                message=message,
                fileUrl=file,
                id_return=id_return,
                user_name=user_name,
                verified=verified,
                avatar=avatar,
                is_read=is_read,
                vote=0,
                edited=False,
                deleted=False
            )

            # Серіалізація даних моделі у JSON
            wrapped_message = schemas.wrap_message(socket_message)
            message_json = wrapped_message.model_dump_json()


            if sender_to_recipient in self.active_connections:
                await self.active_connections[sender_to_recipient].send_text(message_json)

            if recipient_to_sender in self.active_connections:
                await self.active_connections[recipient_to_sender].send_text(message_json)

                logger.info("Notification sent to user")
        except Exception as e:
            logger.error(f"Error sending private message: {e}", exc_info=True)


    @staticmethod
    async def add_private_all_to_database(sender_id: int, receiver_id: int,
                                          message: Optional[str], file: Optional[str],
                                          id_return: Optional[int], is_read: bool):
        try:
            encrypt_message = await async_encrypt(message)
            async with async_session_maker() as session:
                stmt = insert(models.PrivateMessage).values(sender_id=sender_id, receiver_id=receiver_id,message=encrypt_message,
                                                            is_read=is_read, fileUrl=file, id_return=id_return
                                                            )
                result = await session.execute(stmt)
                await session.commit()

                message_id = result.inserted_primary_key[0]
                return message_id
        except Exception as e:
            logger.error(f"Error adding message to database: {e}", exc_info=True)

    @staticmethod
    async def mark_as_sent_message(message_id: int):
        async with async_session_maker() as session:
            await session.execute(
                update(models.PrivateMessage)
                .where(models.PrivateMessage.id == message_id)
                .values(is_sent=True)
            )
            await session.commit()
