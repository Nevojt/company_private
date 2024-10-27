
from typing import List
import logging
from app.models import models
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(filename='_log/func_notification.log', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



async def get_user_fcm_tokens(session: AsyncSession, user_id: int) -> List[str]:
    result = await session.execute(
        select(models.FCMTokenManager.fcm_token).where(models.FCMTokenManager.user_id == user_id)
    )
    tokens = result.scalars().all()
    return tokens



