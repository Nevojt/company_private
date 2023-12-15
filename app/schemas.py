from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime


    
        
class SocketModel(BaseModel):
    created_at: datetime
    receiver_id: int
    message: str
    user_name: str
    avatar: str
    is_read: bool
    
    class Config:
        from_attributes = True

        

    
class TokenData(BaseModel):
    id: Optional[int] = None
    
    
# class UserCreate(BaseModel):
#     email: EmailStr
#     user_name: str
#     password: str
#     avatar: str
    
        
# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str

# class Token(BaseModel):
#     access_token: str
#     token_type: str

        
        



# class UserOut(BaseModel):
#     id: int
#     user_name: str
#     avatar: str
#     created_at: datetime
    
#     class Config:
#         from_attributes = True