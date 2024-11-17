from uuid import UUID
from datetime import datetime
import pytz
from _log_config.log_config import get_logger
from fastapi import WebSocket
from app.database.database import async_session_maker
from app.models import models
from app.schemas import schemas
from sqlalchemy import insert, update
from typing import Dict, Optional, Tuple
from app.security.crypto_messages import async_encrypt

# Налаштування логування
logger = get_logger('connect_manager', 'connect_manager.log')




       # Connecting Private Messages     
class ConnectionManagerPrivate:
    def __init__(self):
        self.active_connections: Dict[Tuple[UUID, UUID], WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID, recipient_id: UUID):
        await websocket.accept()
        self.active_connections[(user_id, recipient_id)] = websocket

    async def disconnect(self, user_id: UUID, recipient_id: UUID):
        self.active_connections.pop((user_id, recipient_id), None)

        
    async def send_private_all(self, message: Optional[str], fileUrl: Optional[str],
                            voiceUrl: Optional[str], videoUrl: Optional[str],
                            sender_id: UUID, receiver_id: UUID,
                            user_name: str, verified: bool,
                            avatar: str, id_return: Optional[UUID],
                            is_read: bool):
        
        sender_to_recipient = (sender_id, receiver_id)
        recipient_to_sender = (receiver_id, sender_id)
        
        timezone = pytz.timezone('UTC')
        current_time_utc = datetime.now(timezone)
        try:
            message_id = await self.add_private_all_to_database(sender_id, receiver_id, message,
                                                                fileUrl, voiceUrl, videoUrl,
                                                                id_return, is_read)
            await self.mark_as_sent_message(message_id)
            # SocketModel
            socket_message = schemas.ChatMessagesSchema(
                created_at=current_time_utc,
                id=message_id,
                receiver_id=sender_id,
                message=message,
                fileUrl=fileUrl,
                voiceUrl=voiceUrl,
                videoUrl=videoUrl,
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
            wrapped_message = await schemas.wrap_message(socket_message)
            message_json = wrapped_message.model_dump_json()


            if sender_to_recipient in self.active_connections:
                await self.active_connections[sender_to_recipient].send_text(message_json)

            if recipient_to_sender in self.active_connections:
                await self.active_connections[recipient_to_sender].send_text(message_json)

                logger.info("Notification sent to user")
        except Exception as e:
            logger.error(f"Error sending private message: {e}", exc_info=True)


    @staticmethod
    async def add_private_all_to_database(sender_id: UUID, receiver_id: UUID,
                                          message: Optional[str], fileUrl: Optional[str],
                                          voiceUrl: Optional[str], videoUrl: Optional[str],
                                          id_return: Optional[int], is_read: bool):
        try:
            encrypt_message = await async_encrypt(message)
            async with async_session_maker() as session:
                stmt = insert(models.PrivateMessage).values(sender_id=sender_id, receiver_id=receiver_id,message=encrypt_message,
                                                            is_read=is_read, fileUrl=fileUrl, voiceUrl=voiceUrl,
                                                            videoUrl=videoUrl, id_return=id_return
                                                            )
                result = await session.execute(stmt)
                await session.commit()

                message_id = result.inserted_primary_key[0]
                return message_id
        except Exception as e:
            logger.error(f"Error adding message to database: {e}", exc_info=True)

    @staticmethod
    async def mark_as_sent_message(message_id: UUID):
        async with async_session_maker() as session:
            await session.execute(
                update(models.PrivateMessage)
                .where(models.PrivateMessage.id == message_id)
                .values(is_sent=True)
            )
            await session.commit()
