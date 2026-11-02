from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    department_id: int
    department_name: str
