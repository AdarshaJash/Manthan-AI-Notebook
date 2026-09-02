from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str
    grade: str

class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    grade: str = Field(default="Student", max_length=80)

class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)

class AuthResponse(BaseModel):
    token: str
    user: UserOut
