
import logging
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import and_, asc, or_, update, func
from app import models, schemas
from app.config import settings

from app.AI import sayory

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



async def fetch_last_private_messages(session: AsyncSession, sender_id: int, receiver_id: int) -> List[dict]:
    
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

        message_data = {
            "created_at": private.created_at,
            "id": private.id,
            "receiver_id": private.sender_id,
            "message": decrypted_message,
            "fileUrl": private.fileUrl,
            "id_return": private.id_return,
            "user_name": user.user_name,
            "verified": user.verified,
            "avatar": user.avatar,
            "is_read": private.is_read,
            "vote": votes,
            "edited": private.edited
        }
        try:
            messages.append(schemas.SocketModel(**message_data))
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Data validation error: {str(e)}")
            
    messages.reverse()  # Optionally reverse the list if needed
    return messages




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
    
    
async def process_vote(vote: schemas.Vote, session: AsyncSession, current_user: models.User):
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

        
        
async def change_message(id_messages: int, message_update: schemas.SocketUpdate,
                         session: AsyncSession, 
                         current_user: models.User):
    
    
    query = select(models.PrivateMessage).where(models.PrivateMessage.id == id_messages, models.PrivateMessage.sender_id == current_user.id)
    result = await session.execute(query)
    messages = result.scalar()

    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or you don't have permission to edit this message")

    messages.message = message_update.message
    messages.edited = True
    session.add(messages)
    await session.commit()

    return {"message": "Message updated successfully"}


async def delete_message(id_message: int,
                         session: AsyncSession, 
                         current_user: models.User):
    
    
    query = select(models.PrivateMessage).where(models.PrivateMessage.id == id_message, models.PrivateMessage.sender_id == current_user.id)
    result = await session.execute(query)
    message = result.scalar()

    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found or you don't have permission to delete this message")

    await session.delete(message)
    await session.commit()

    return {"message": "Message deleted successfully"}


    
