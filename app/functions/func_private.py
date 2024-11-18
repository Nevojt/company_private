import asyncio
from uuid import UUID
from _log_config.log_config import get_logger
from fastapi import HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import and_, asc, or_, update, func

from app.database.database import async_session_maker
from app.models import models
from app.schemas import schemas
from app.schemas.schemas import ChatMessagesSchema
from app.security.crypto_messages import async_decrypt
from app.settings.config import settings


logger = get_logger('func_private', 'func_private.log')



async def fetch_last_private_messages(sender_id: UUID, receiver_id: UUID,
                                      session: AsyncSession) -> list[ChatMessagesSchema]:
    
    """
    Fetch the last private messages between two users from the database.

    Args:
    session (AsyncSession): The database session to execute the query.
    sender_id (int): The ID of the user who sent the message.
    receiver_id (int): The ID of the user who received the message.

    Returns:
    List[dict]: A list of dictionaries containing message details.
    """
    try:
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
                schemas.ChatMessagesSchema(
                    created_at=private.created_at,
                    id=private.id,
                    receiver_id=private.sender_id,
                    message=decrypted_message,
                    fileUrl=private.fileUrl,
                    voiceUrl=private.voiceUrl,
                    videoUrl=private.videoUrl,
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
    except Exception as e:
        logger.error(f"Error fetching last private messages: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error fetching last private messages")



async def send_messages_via_websocket(messages, websocket):
    try:
        for message in messages:
            wrapped_message = await schemas.wrap_message(message)
            json_message = wrapped_message.model_dump_json()
            await websocket.send_text(json_message)
    except Exception as e:
        logger.error(f"Error sending messages via websocket: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error sending messages via websocket")


async def fetch_one_message(message_id: int, session: AsyncSession): #-> schemas.SocketModel:
    """
    Fetch a single private message from the database.

    Args:
    message_id (int): The ID of the message to fetch.
    """
    try:
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

            message = schemas.ChatMessagesSchema(
                created_at=private.created_at,
                id=private.id,
                receiver_id=private.sender_id,
                message=decrypted_message,
                fileUrl=private.fileUrl,
                voiceUrl=private.voiceUrl,
                videoUrl=private.videoUrl,
                id_return=private.id_return,
                user_name=user.user_name if user is not None else "Unknown user",
                verified=user.verified,
                avatar=user.avatar if user is not None else "https://tygjaceleczftbswxxei.supabase.co/storage/v1/object/public/image_bucket/inne/image/photo_2024-06-14_19-20-40.jpg",
                is_read=private.is_read,
                vote=votes,
                edited=private.edited,
                deleted=private.deleted
            )
            wrapped_message_update = await schemas.wrap_message_update(message)
            return wrapped_message_update.model_dump_json()

        else:
            raise HTTPException(status_code=404, detail="Message not found")
    except Exception as e:
        logger.error(f"Error fetching one message: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to fetch message id  {e}")



async def get_recipient_by_id(receiver_id: UUID, session: AsyncSession):
    try:
        recipient = await session.execute(select(models.User).filter(models.User.id == receiver_id))
        result = recipient.scalars().first()

        return result
    except Exception as e:
        logger.error(f"Error fetching recipient by ID: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to get recipient id  {e}")



async def mark_messages_as_read(user_id: UUID, sender_id: UUID):
    """
    Marks all private messages sent by a specific user as unread for a specific recipient.

    Args:

        user_id (int): The ID of the recipient.
        sender_id (int): The ID of the user who sent the messages.

    Returns:
        None

    Raises:
        HTTPException: If an error occurs while updating the database.
    """
    async with async_session_maker() as session:
        try:
            await session.execute(
                update(models.PrivateMessage)
                .where(models.PrivateMessage.receiver_id == user_id,
                       models.PrivateMessage.is_read).filter(models.PrivateMessage.sender_id == sender_id)
                .values(is_read=False)
            )
            await session.commit()
        except Exception as e:
            logger.error(f"Error marking messages as read: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Failed to mark messages as read {e}")
    
vote_lock = asyncio.Lock()
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
    async with vote_lock:
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
                    return {"notice": "Successfully removed vote"}
                else:
                    # If vote does not exist, add it
                    new_vote = models.PrivateMessageVote(message_id=vote.message_id,
                                                         user_id=current_user.id,
                                                         dir=vote.dir)
                    session.add(new_vote)
                    await session.commit()
                    return {"notice": "Successfully added vote"}

            else:
                if not found_vote:
                    return {"notice": "Vote does not exist or has already been removed"}

                # Remove the vote
                await session.delete(found_vote)
                await session.commit()
                return {"notice": "Successfully deleted vote"}

        except HTTPException as http_exc:
            logger.error(f"HTTP error occurred: {http_exc.detail}")
            raise http_exc

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"An unexpected error occurred {e}")



async def change_message(message_id: UUID, message_update: schemas.ChatUpdateMessage,
                         session: AsyncSession,
                         current_user: models.User):

    try:
        query = select(models.PrivateMessage).where(models.PrivateMessage.id == message_id,
                                                    models.PrivateMessage.sender_id == current_user.id)
        result = await session.execute(query)
        messages = result.scalar()

        if not messages:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Message not found or you don't have permission to edit this message")

        if messages.deleted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Message has been deleted")

        messages.message = message_update.message
        messages.edited = True
        session.add(messages)
        await session.commit()

        return {"notice": "Message updated successfully"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred update(change message)")


async def delete_message(message_id: UUID,
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
    try:
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
        return str(message_id)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred delete message")


async def get_message_by_id(message_id: UUID, user_id: UUID,
                            session: AsyncSession):
    try:
        message_query = select(models.PrivateMessage).where(models.PrivateMessage.id == message_id,
                                                            models.PrivateMessage.receiver_id == user_id)
        message_result = await session.execute(message_query)
        return message_result.scalar()
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Error getting message id")
    
async def get_sayory(session: AsyncSession):
    sayory = settings.sayory
    sayory_query = select(models.User).where(models.User.user_name == sayory)
    sayory_result = await session.execute(sayory_query)
    return sayory_result.scalar_one_or_none()