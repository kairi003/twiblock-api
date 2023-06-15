from typing import Optional
import requests
import tweepy
from fastapi import FastAPI
from pydantic import BaseModel, Json, validator
from tweepy_authlib import CookieSessionUserHandler


class AuthInfo(BaseModel):
    screen_name: str
    password: str
    cookies_json: Optional[Json[dict]] = None


class BaseRequest(BaseModel):
    auth: AuthInfo
    logout: bool = False


class BaseResponse(BaseModel):
    cookies_json: Optional[Json[dict]] = None


class CreateBlockParams(BaseModel):
    screen_name: Optional[str] = None
    user_id: Optional[str] = None
    include_entities: bool = True
    skip_status: bool = False

    @validator('screen_name, user_id')
    def check_params(cls, v, values):
        if v is None:
            if values['screen_name'] is None and values['user_id'] is None:
                raise ValueError('screen_name or user_id must be specified')
        return v


class CreateBlockRequest(BaseRequest):
    params: CreateBlockParams


app = FastAPI()


@app.get("/")
async def root():
    return {"greeting": "Hello world"}


@app.post("/create-block", response_model=BaseResponse)
async def create_block(req: CreateBlockRequest):
    auth_handler = get_auth_handler(req.auth)
    api = tweepy.API(auth_handler)
    api.create_block(**req.params.dict())
    cookies = api.session.cookies.get_dict()
    if req.logout:
        auth_handler.logout()
        cookies = None
    return BaseResponse(cookies_json=cookies)


def get_auth_handler(auth: AuthInfo) -> CookieSessionUserHandler:
    if auth.cookies_json is not None:
        try:
            res = requests.get("https://tweetdeck.twitter.com/",
                               cookies=auth.cookies_json)
            if "twid" in res.cookies:
                raise ValueError("Invalid cookie")
            return CookieSessionUserHandler(cookies=res.cookies)
        except Exception as e:
            pass
    auth_handler = CookieSessionUserHandler(
        screen_name=auth.screen_name, password=auth.password)
    return auth_handler
