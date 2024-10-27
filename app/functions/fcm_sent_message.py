
import logging

from .func_notifications import get_user_fcm_tokens
from sqlalchemy.ext.asyncio import AsyncSession


import firebase_admin
from firebase_admin import credentials, messaging
from app.settings.config import settings

# Initialize the Firebase app with service account credentials
cred = credentials.Certificate(settings.google_services)
result = firebase_admin.initialize_app(cred)


# Configure logging
logging.basicConfig(filename='_log/notification.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# @router.post("/send_notification")
async def send_notifications_to_user(
    message: str,
    sender: str,
    recipient_id: int,
    session: AsyncSession
):
    try:
        fcm_tokens = await get_user_fcm_tokens(session, recipient_id)

        message = messaging.Message(
            notification=messaging.Notification(
                title=sender,
                body=message,
            ),
            token=fcm_tokens[0]
        )
        print(message)
        # response = messaging.send_each(message)
        response = messaging.send(message)
        print(response)

        logger.info("Notifications sent to user")
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")