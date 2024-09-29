
from sqlalchemy import update
from app import models
from app.functions.func_private import mark_messages_as_read





async def test_mark_messages_as_read(mocker, session, user):
    # Mocking the execute method of the session
    mocker.patch.object(session, 'execute')

    # Marking all messages as read for the given user
    await mark_messages_as_read(session, user.id)

    # Asserting that the execute method was called with the correct query
    session.execute.assert_called_once_with(
        update(models.PrivateMessage)
        .where(models.PrivateMessage.recipient_id == user.id,
               models.PrivateMessage.is_read == True)
        .values(is_read=False)
    )