import asyncio
from _log_config.log_config import get_logger
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi import BackgroundTasks
from app.connect.connection_manager import ConnectionManagerPrivate
from app.database.database import get_async_session
from app.schemas import schemas
from ..security import oauth2
from sqlalchemy.ext.asyncio import AsyncSession
from app.functions.func_private import (change_message, delete_message, fetch_last_private_messages,
                                        mark_messages_as_read, process_vote, get_recipient_by_id,
                                        send_messages_via_websocket, fetch_one_message, get_sayory)
from app.functions.fcm_sent_message import send_notifications_private_message
from app.AI.sayory import ask_to_gpt

# Налаштування логування
logger = get_logger('private_message', 'private_message.log')

router = APIRouter()
manager = ConnectionManagerPrivate()




    

@router.websocket("/private/{receiver_id}")
async def web_private_endpoint(background_tasks: BackgroundTasks,
                            websocket: WebSocket,
                            receiver_id: UUID,
                            token: str,
                            session: AsyncSession = Depends(get_async_session)
                            ):
    
    """
    WebSocket endpoint for handling private messaging between users.

    Args:
    websocket (WebSocket): The WebSocket connection instance.
    recipient_id (int): The ID of the message recipient.
    token (str): The authentication token of the current user.
    session (AsyncSession): The database session, injected by dependency.

    Operations:
    - Authenticates the current user.
    - Establishes a WebSocket connection.
    - Fetches and sends the last private messages to the connected client.
    - Listens for incoming messages and handles sending and receiving of private messages.
    - Disconnects on WebSocket disconnect event.
    """
    
    try:
        user = await oauth2.get_current_user(token, session)
        recipient = await get_recipient_by_id(receiver_id, session)
        if not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Recipient not found.")
    except Exception as error_get_user:
        logger.error(f"Error getting user: {error_get_user}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
   
    await manager.connect(websocket, user.id, receiver_id)
    await mark_messages_as_read(user.id, receiver_id)

    messages = await fetch_last_private_messages(receiver_id, user.id, session)

    await send_messages_via_websocket(messages, websocket)
    
    async def periodic_task():
        while True:
            await mark_messages_as_read(user.id, receiver_id)
            await asyncio.sleep(1) 
    
    task = asyncio.create_task(periodic_task())

    try:
        while True:
            data = await websocket.receive_json()

            # Created likes
            if 'vote' in data:
                try:
                    vote_data = schemas.Vote(**data['vote'])
                    await process_vote(vote_data, session, user)
                 
                    message_json = await fetch_one_message(vote_data.message_id, session)
                    await websocket.send_text(message_json)

                except Exception as e:
                    logger.error(f"Error processing vote: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error processing vote: {e}"})

            elif 'update' in data:
                try:
                    message_data = schemas.ChatUpdateMessage(**data['update'])
                    await change_message(message_data.id, message_data, session, user)

                    message_json = await fetch_one_message(message_data.id, session)
                    await websocket.send_text(message_json)

                except Exception as e:
                    logger.error(f"Error processing Update: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error processing update: {e}"})
                
            # Block delete message       
            elif 'delete' in data:
                try:
                    message_data = schemas.ChatMessageDelete(**data['delete'])
                    message_id = await delete_message(message_data.id, session, user)
                    await websocket.send_json({"deleted": {"id": message_id}})


                except Exception as e:
                    logger.error(f"Error processing delete: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error processing delete: {e}"})

            elif 'send' in data:
                
                message_data = data['send']
                original_message_id = message_data['original_message_id']
                original_message = message_data['message']
                file_url = message_data['fileUrl']
                voice_url = message_data['voiceUrl']
                video_url = message_data['videoUrl']
                    
                try:

                    await manager.send_private_all(
                        message=original_message,
                        fileUrl=file_url,
                        voiceUrl=voice_url,
                        videoUrl=video_url,
                        receiver_id=receiver_id,
                        sender_id=user.id,
                        user_name=user.user_name,
                        avatar=user.avatar,
                        verified=user.verified,
                        id_return=original_message_id,
                        is_read=True
                    )
                    await mark_messages_as_read(user.id, receiver_id)

                    background_tasks.add_task(await send_notifications_private_message(message=original_message,
                                                                                      sender=user.user_name,
                                                                                      recipient_id=receiver_id,
                                                                                      session=session))


                    logger.info(f"Sent message: {original_message}")
                except Exception as e:
                    logger.error(f"Error sending message: {e}", exc_info=True)
                    await websocket.send_json({"notice": f"Error sending message: {e}"})

                sayory = await get_sayory(session)
                if receiver_id == sayory.id:
                    try:
                        response_sayory = await ask_to_gpt(original_message)
                        
                        for message in response_sayory:
                            await manager.send_private_all(
                                message=message,
                                fileUrl=file_url,
                                voiceUrl=voice_url,
                                videoUrl=video_url,
                                receiver_id=user.id,
                                sender_id=receiver_id,
                                user_name="SayOry",
                                avatar="https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/girl_5.webp",
                                verified=True,
                                id_return=original_message_id,
                                is_read=True
                            )
                            await asyncio.sleep(1)
                        await mark_messages_as_read(user.id, receiver_id)
                        logger.info(f"Sent GPT response: {response_sayory}")
                    except Exception as e:
                        logger.error(f"Error processing GPT query: {e}", exc_info=True)
                        await websocket.send_json({"notice": f"Error processing GPT query: {e}"})
                        
                
                                            
    except WebSocketDisconnect:
        task.cancel()
        await manager.disconnect(user.id, receiver_id)
    finally:
        await session.close()
        print("Session closed")


