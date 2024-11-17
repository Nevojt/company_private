
from _log_config.log_config import get_logger
from uuid import UUID
from .func_notifications import get_user_fcm_tokens
from sqlalchemy.ext.asyncio import AsyncSession

import firebase_admin
from firebase_admin import credentials, messaging
from app.settings.config import settings

# Initialize the Firebase app with service account credentials
cred = credentials.Certificate(settings.google_services)
result = firebase_admin.initialize_app(cred)


# Configure logging
logger = get_logger('notification', 'notification.log')


# @router.post("/send_notification")
async def send_notifications_private_message(
    message: str,
    sender: str,
    recipient_id: UUID,
    session: AsyncSession
):
    try:
        fcm_tokens = await get_user_fcm_tokens(recipient_id, session)
        if not fcm_tokens:
            logger.info("No FCM tokens found for user")
            return
        for token in fcm_tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=sender,
                    body=message,
                ),
                token=token
            )
            response = messaging.send(message)

        logger.info("Notifications sent to user")
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")