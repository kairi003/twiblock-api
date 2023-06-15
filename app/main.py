import os
from typing import Optional, Any
import requests
import tweepy
from fastapi import FastAPI, Request, HTTPException
from pydantic import Field, BaseModel, root_validator
from tweepy_authlib import CookieSessionUserHandler


class AuthInfo(BaseModel):
    """Twitter auth info"""
    screen_name: str = Field(..., description="Twitter screen name without @")
    password: str = Field(..., description="Twitter password")
    cookies: Optional[dict[str, str]] = Field(
        None, description="Twitter cookies json")


class BaseRequest(BaseModel):
    """Base Request Model"""
    auth: AuthInfo = Field(..., description="Twitter auth info")
    logout: bool = Field(False, description="Logout after process")


class BaseResponse(BaseModel):
    """Base Response Model"""
    cookies: Optional[dict[str, str]] = Field(
        None, description="Twitter cookies json")
    response: Optional[dict[str, Any]] = Field(
        None, description="Twitter api response")


class CreateBlockParams(BaseModel):
    """
    Parameters for API.create_block

    screen_name or user_id must be specified
    """
    screen_name: Optional[str] = Field(
        None, description="Twitter screen name without @")
    user_id: Optional[str] = Field(None, description="Twitter user id")
    include_entities: bool = Field(
        False, description="If True, include entries nodes (defaults: False)")
    skip_status: bool = Field(
        True, description="If True, statuses will not be included in the returned user objects (defaults: True)")

    @root_validator
    def check_params(cls, values: dict):
        if (values.get('screen_name') or values.get('user_id')) is None:
            raise ValueError('screen_name or user_id must be specified')
        return values


class CreateBlockRequest(BaseRequest):
    params: CreateBlockParams


app = FastAPI(debug=os.environ.get("DEBUG", False))


@app.get("/")
async def root():
    return {"greeting": "Hello world"}


@app.post("/login", response_model=AuthInfo)
async def login(auth: AuthInfo) -> AuthInfo:
    auth_handler = get_auth_handler(auth)
    auth.cookies = auth_handler.get_cookies().get_dict()
    return auth


@app.post("/create-block", response_model=BaseResponse)
async def create_block(req: CreateBlockRequest):
    auth_handler = get_auth_handler(req.auth)
    try:
        api = tweepy.API(auth_handler)
        res: tweepy.User = api.create_block(**req.params.dict())
        cookies = auth_handler.get_cookies().get_dict()
    except Exception as e:
        auth_handler.logout()
        raise e
    if req.logout:
        auth_handler.logout()
        cookies = None
    return BaseResponse(cookies=cookies, response=res._json)


def get_auth_handler(auth: AuthInfo) -> CookieSessionUserHandler:
    if auth.cookies is not None:
        ses = requests.Session()
        ses.cookies.update(auth.cookies)
        ses.get("https://tweetdeck.twitter.com/")
        if "twid" in ses.cookies:
            return CookieSessionUserHandler(cookies=ses.cookies)
    return CookieSessionUserHandler(screen_name=auth.screen_name, password=auth.password)


@app.exception_handler(tweepy.TweepyException)
async def handle_tweepy_exception(request: Request, exc: tweepy.TweepyException):
    raise HTTPException(status_code=401, detail=str(exc))
