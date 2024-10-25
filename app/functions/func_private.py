
import logging
from fastapi import HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict
from sqlalchemy import and_, asc, or_, update, func
from app.models import models
from app.schemas import schemas
from app.schemas.schemas import SocketModel
from app.settings.config import settings

import base64
from cryptography.fernet import Fernet, InvalidToken

# Ініціалізація шифрувальника
key = settings.key_crypto
cipher = Fernet(key)

def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)).decode('utf-8') == s
    except Exception:
        return False

async def async_encrypt(data: Optional[str]):
    if data is None:
        return None
    
    encrypted = cipher.encrypt(data.encode())
    encoded_string = base64.b64encode(encrypted).decode('utf-8')
    return encoded_string

async def async_decrypt(encoded_data: Optional[str]):
    if encoded_data is None:
        return None
    
    if not is_base64(encoded_data):
        return encoded_data

    try:
        encrypted = base64.b64decode(encoded_data.encode('utf-8'))
        decrypted = cipher.decrypt(encrypted).decode('utf-8')
        return decrypted
    except InvalidToken:
        return None  
    
logging.basicConfig(filename='_log/func_vote.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



async def fetch_last_private_messages(session: AsyncSession, sender_id: int, receiver_id: int) -> list[SocketModel]:
    
    """
    Fetch the last private messages between two users from the database.

    Args:
    session (AsyncSession): The database session to execute the query.
    sender_id (int): The ID of the user who sent the message.
    receiver_id (int): The ID of the user who received the message.

    Returns:
    List[dict]: A list of dictionaries containing message details.
    """
    
    query = select(
        models.PrivateMessage,
        models.User,
        func.coalesce(func.sum(models.PrivateMessageVote.dir), 0).label('vote')
    ).join(
        models.User, models.PrivateMessage.sender_id == models.User.id
    ).outerjoin(
        models.PrivateMessageVote, models.PrivateMessage.id == models.PrivateMessageVote.message_id
    ).where(
        or_(
            and_(models.PrivateMessage.sender_id == sender_id, models.PrivateMessage.receiver_id == receiver_id),
            and_(models.PrivateMessage.sender_id == receiver_id, models.PrivateMessage.receiver_id == sender_id)
            )
    ).group_by(
        models.PrivateMessage.id, models.User.id
    ).order_by(asc(models.PrivateMessage.id))
               
    result = await session.execute(query)
    raw_messages = result.all()

    messages = []
    for private, user, votes in raw_messages:
        decrypted_message = await async_decrypt(private.message)
        if decrypted_message is None:
            decrypted_message = None

        messages.append(
            schemas.SocketModel(
                created_at=private.created_at,
                id=private.id,
                receiver_id=private.sender_id,
                message=decrypted_message,
                fileUrl=private.fileUrl,
                id_return=private.id_return,
                user_name=user.user_name if user is not None else "Unknown user",
                verified=user.verified,
                avatar=user.avatar if user is not None else "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/photo_2024-06-14_19-20-40.jpg",
                is_read=private.is_read,
                vote=votes,
                edited=private.edited,
                deleted=private.deleted
            )
        )
    # messages.reverse()
    return messages

async def send_messages_via_websocket(messages, websocket):
    for message in messages:
        wrapped_message = schemas.wrap_message(message)
        json_message = wrapped_message.model_dump_json()
        await websocket.send_text(json_message)


async def fetch_one_message(message_id: int, session: AsyncSession): #-> schemas.SocketModel:
    query = select(
        models.PrivateMessage,
        models.User,
        func.coalesce(func.sum(models.PrivateMessageVote.dir), 0).label('votes')
    ).outerjoin(
        models.PrivateMessageVote, models.PrivateMessage.id == models.PrivateMessageVote.message_id
    ).outerjoin(
        models.User, models.PrivateMessage.sender_id == models.User.id
    ).filter(
        models.PrivateMessage.id == message_id
    ).group_by(
        models.PrivateMessage.id, models.User.id
    )

    result = await session.execute(query)
    raw_message = result.first()

    # Convert raw messages to SocketModel
    if raw_message:
        private, user, votes = raw_message
        decrypted_message = await async_decrypt(private.message)

        message = schemas.SocketModel(
            created_at=private.created_at,
            id=private.id,
            receiver_id=private.sender_id,
            message=decrypted_message,
            fileUrl=private.fileUrl,
            id_return=private.id_return,
            user_name=user.user_name if user is not None else "Unknown user",
            verified=user.verified,
            avatar=user.avatar if user is not None else "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/photo_2024-06-14_19-20-40.jpg",
            is_read=private.is_read,
            vote=votes,
            edited=private.edited,
            deleted=private.deleted
        )
        wrapped_message_update = schemas.wrap_message_update(message)
        return wrapped_message_update.model_dump_json()

    else:
        raise HTTPException(status_code=404, detail="Message not found")



async def get_recipient_by_id(session: AsyncSession, receiver_id: id):
    recipient = await session.execute(select(models.User).filter(models.User.id == receiver_id))
    result = recipient.scalars().first()
    
    return result   


async def unique_user_name_id(user_id: int, user_name: str):
    unique_user_name_id = f"{user_id}-{user_name}"

    
    return unique_user_name_id



async def mark_messages_as_read(session: AsyncSession, user_id: int, sender_id: int):
    """
    Marks all private messages sent by a specific user as unread for a specific recipient.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The ID of the recipient.
        sender_id (int): The ID of the user who sent the messages.

    Returns:
        None

    Raises:
        HTTPException: If an error occurs while updating the database.
    """
    await session.execute(
        update(models.PrivateMessage)
        .where(models.PrivateMessage.receiver_id == user_id,
               models.PrivateMessage.is_read == True).filter(models.PrivateMessage.sender_id == sender_id)
        .values(is_read=False)
    )
    await session.commit()
    
    
async def process_vote(vote: schemas.Vote,
                       session: AsyncSession,
                       current_user: models.User):
    """
    Processes a vote submitted by a user.

    Args:
        vote (schemas.Vote): The vote submitted by the user.
        session (AsyncSession): The database session.
        current_user (models.User): The current user.

    Returns:
        dict: A message indicating the result of the vote.

    Raises:
        HTTPException: If an error occurs while processing the vote.
    """
    try:
        # Check if the message exists
        result = await session.execute(select(models.PrivateMessage).filter(models.PrivateMessage.id == vote.message_id))
        message = result.scalars().first()
        
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Message with id: {vote.message_id} does not exist")
        if message.deleted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Message has been deleted")
        
        # Check if the user has already voted on this message
        vote_result = await session.execute(select(models.PrivateMessageVote).filter(
            models.PrivateMessageVote.message_id == vote.message_id, 
            models.PrivateMessageVote.user_id == current_user.id
        ))
        found_vote = vote_result.scalars().first()
        
        # Toggle vote logic
        if vote.dir == 1:
            if found_vote:
                # If vote exists, remove it
                await session.delete(found_vote)
                await session.commit()
                return {"message": "Successfully removed vote"}
            else:
                # If vote does not exist, add it
                new_vote = models.PrivateMessageVote(message_id=vote.message_id, user_id=current_user.id, dir=vote.dir)
                session.add(new_vote)
                await session.commit()
                return {"message": "Successfully added vote"}

        else:
            if not found_vote:
                return {"message": "Vote does not exist or has already been removed"}
            
            # Remove the vote
            await session.delete(found_vote)
            await session.commit()
            return {"message": "Successfully deleted vote"}

    except HTTPException as http_exc:
        logger.error(f"HTTP error occurred: {http_exc.detail}")
        raise http_exc
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred")



async def change_message(message_id: int, message_update: schemas.SocketUpdate,
                         session: AsyncSession,
                         current_user: models.User):


    query = select(models.PrivateMessage).where(models.PrivateMessage.id == message_id, models.PrivateMessage.sender_id == current_user.id)
    result = await session.execute(query)
    messages = result.scalar()

    if not messages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or you don't have permission to edit this message")

    if messages.deleted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Message has been deleted")

    messages.message = message_update.message
    messages.edited = True
    session.add(messages)
    await session.commit()

    return {"message": "Message updated successfully"}


async def delete_message(message_id: int,
                         session: AsyncSession,
                         current_user: models.User):
    """
    Delete a message from the database.

    Args:
        message_id (int): The ID of the message to delete.
        session (AsyncSession): The database session.
        current_user (models.User): The current user.

    Returns:
        Dict[str, Any]: A response indicating whether the message was deleted and any errors that may have occurred.

    Raises:
        HTTPException: If an error occurs while deleting the message.
    """
    query = select(models.PrivateMessage).where(models.PrivateMessage.id == message_id,
                                                models.PrivateMessage.sender_id == current_user.id)
    result = await session.execute(query)
    message = result.scalar()

    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Message not found or you don't have permission to delete this message")

    message.message = None
    message.fileUrl = None
    message.id_return = None
    message.deleted = True

    vote_result = await session.execute(select(models.PrivateMessageVote).filter(
        models.PrivateMessageVote.message_id == message_id,
        models.PrivateMessageVote.user_id == current_user.id
    ))
    found_vote = vote_result.scalars().all()
    for vote in found_vote:
        await session.delete(vote)

    session.add(message)
    await session.commit()
    return message_id


async def get_message_by_id(message_id: int, user_id: int, session: AsyncSession):
    message_query = select(models.PrivateMessage).where(models.PrivateMessage.id == message_id, models.PrivateMessage.receiver_id == user_id)
    message_result = await session.execute(message_query)
    return message_result.scalar()
    
