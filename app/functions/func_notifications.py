from uuid import UUID
from typing import List
from _log_config.log_config import get_logger
from app.models import models
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession


logger = get_logger('func_notification', 'func_notification.log')



async def get_user_fcm_tokens(user_id: UUID, session: AsyncSession, ) -> List[str]:
    result = await session.execute(
        select(models.FCMTokenManager.fcm_token).where(models.FCMTokenManager.user_id == user_id)
    )
    tokens = result.scalars().all()
    return tokens



