import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from app.connect.connection_manager import ConnectionManagerPrivate
from app.database.database import get_async_session
from app.schemas import schemas
from ..security import oauth2
from sqlalchemy.ext.asyncio import AsyncSession
from app.functions.func_private import change_message, delete_message, fetch_last_private_messages, mark_messages_as_read, process_vote
from app.functions.func_private import get_recipient_by_id, send_messages_via_websocket, fetch_one_message
from app.AI import sayory

# Налаштування логування
logging.basicConfig(filename='_log/private_message.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter()
manager = ConnectionManagerPrivate()




    

@router.websocket("/private/{receiver_id}")
async def web_private_endpoint(
    websocket: WebSocket,
    receiver_id: int,
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
    
    
    user = await oauth2.get_current_user(token, session)
    recipient = await get_recipient_by_id(session, receiver_id)
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recipient not found.")
   
    await manager.connect(websocket, user.id, receiver_id)
    await mark_messages_as_read(session, user.id, receiver_id)

    messages = await fetch_last_private_messages(session, user.id, receiver_id)
    # messages.reverse()
    await send_messages_via_websocket(messages, websocket)

    #
    #
    # for message in messages:
    #     message_json = message.json()
    #     await websocket.send_text(message_json)
    
    async def periodic_task():
        while True:
            await mark_messages_as_read(session, user.id, receiver_id)
            await asyncio.sleep(1)  # чекає 1 секунду
    
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
                    await websocket.send_json({"message": f"Error processing vote: {e}"})

            elif 'update' in data:
                try:
                    message_data = schemas.SocketUpdate(**data['update'])
                    await change_message(message_data.id, message_data, session, user)

                    message_json = await fetch_one_message(message_data.id, session)
                    await websocket.send_text(message_json)

                except Exception as e:
                    logger.error(f"Error processing Update: {e}", exc_info=True)
                    await websocket.send_json({"message": f"Error processing update: {e}"})
                
            # Block delete message       
            elif 'delete' in data:
                try:
                    message_data = schemas.SocketDelete(**data['delete'])
                    message_id = await delete_message(message_data.id, session, user)
                    # await websocket.send_json({"delete": {"id": message_id}})
                    await websocket.send_json({"message": "deleted"})

                except Exception as e:
                    logger.error(f"Error processing delete: {e}", exc_info=True)
                    await websocket.send_json({"message": f"Error processing delete: {e}"})

            elif 'send' in data:
                
                message_data = data['send']
                original_message_id = message_data['original_message_id']
                original_message = message_data['message']
                file_url = message_data['fileUrl']
                    
                try:

                    await manager.send_private_all(
                        message=original_message,
                        file=file_url,
                        receiver_id=receiver_id,
                        sender_id=user.id,
                        user_name=user.user_name,
                        avatar=user.avatar,
                        verified=user.verified,
                        id_return=original_message_id,
                        is_read=True
                    )
                    await mark_messages_as_read(session, user.id, receiver_id)
                    logger.info(f"Sent message: {original_message}")
                except Exception as e:
                    logger.error(f"Error sending message: {e}", exc_info=True)
                    await websocket.send_json({"message": f"Error sending message: {e}"})

                if receiver_id == 2:
                    try:
                        response_sayory = await sayory.ask_to_gpt(original_message)
                        
                        for message in response_sayory:
                            await manager.send_private_all(
                                message=message,
                                file=file_url,
                                receiver_id=user.id,
                                sender_id=receiver_id,
                                user_name="SayOry",
                                avatar="https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/girl_5.webp",
                                verified=True,
                                id_return=original_message_id,
                                is_read=True
                            )
                            await asyncio.sleep(1)
                        await mark_messages_as_read(session, user.id, receiver_id)
                        logger.info(f"Sent GPT response: {response_sayory}")
                    except Exception as e:
                        logger.error(f"Error processing GPT query: {e}", exc_info=True)
                        await websocket.send_json({"message": f"Error processing GPT query: {e}"})
                        
                
                                            
    except WebSocketDisconnect:
        task.cancel()
        await manager.disconnect(user.id, receiver_id)
    finally:
        await session.close()
        print("Session closed")


