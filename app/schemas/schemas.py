from typing import Optional
from pydantic import BaseModel, Field
from typing import Annotated
from datetime import datetime



    
        
class SocketModel(BaseModel):
    created_at: datetime
    id: int
    receiver_id: int
    message: Optional[str] = None
    fileUrl: Optional[str] = None
    id_return: Optional[int] = None
    user_name: str
    verified: bool
    avatar: str
    is_read: bool
    vote: int
    edited: bool
    deleted: bool

    # Send message to chat
class WrappedSocketMessage(BaseModel):
    message: SocketModel

def wrap_message(socket_model_instance: SocketModel) -> WrappedSocketMessage:
    return WrappedSocketMessage(message=socket_model_instance)

# Update message in chat
class WrappedUpdateMessage(BaseModel):
    update: SocketModel

def wrap_message_update(socket_model_update: SocketModel) -> WrappedUpdateMessage:
    return WrappedUpdateMessage(update=socket_model_update)

class SocketUpdate(BaseModel):
    id: int
    message: str
    
class SocketDelete(BaseModel):
    id: int

    
class TokenData(BaseModel):
    id: Optional[int] = None
    
class Vote(BaseModel):
    message_id: int
    dir: Annotated[int, Field(strict=True, le=1)]
    
