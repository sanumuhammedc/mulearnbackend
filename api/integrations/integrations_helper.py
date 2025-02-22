from datetime import datetime, timedelta

import decouple
import jwt
import pytz
import requests

from db.integrations import Integration
from mulearnbackend.settings import SECRET_KEY
from utils.response import CustomResponse


def get_authorization_id(token: str) -> str | None:
    """
    The function `get_authorization_id` decodes a JWT token and returns the authorization ID if the
    token is valid and has not expired, otherwise it returns None.

    :param token: The `token` parameter is a JSON Web Token (JWT) that is used for authentication and
    authorization purposes. It is a string that contains encoded information about the user or client
    making the request
    :return: the authorization ID if the token is valid and has not expired. If the token is invalid or
    has expired, it returns None.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    authorization_id = payload.get("authorization_id")
    exp_timestamp = payload.get("exp", 0)

    if exp_timestamp and datetime.now(pytz.utc) < datetime.fromtimestamp(
            exp_timestamp, tz=pytz.utc
    ):
        return authorization_id
    else:
        raise ValueError("Token invalid or expired")


def generate_confirmation_token(authorization_id: str) -> str:
    """
    The function generates a confirmation token using the authorization ID and expiration time.

    :param authorization_id: The `authorization_id` parameter is the unique identifier for the
    authorization. It is used to associate the token with a specific authorization in your system
    :return: a confirmation token, which is a JSON Web Token (JWT) encoded with the given payload and
    using the HS256 algorithm.
    """
    expiration_time = datetime.now(pytz.utc) + timedelta(hours=1)

    payload = {
        "authorization_id": authorization_id,
        "exp": expiration_time,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def token_required(integration_name: str):
    """
    The `token_required` function is a decorator that checks if a valid token is present in the
    Authorization header of a request, and if so, verifies that the token belongs to a specific
    integration.

    :param integration_name: The `integration_name` parameter is a string that represents the name of
    the integration that the token is required for
    :return: The function `token_required` returns a decorator function.
    """

    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            try:
                auth_header = request.META.get("HTTP_AUTHORIZATION")
                if not auth_header or not auth_header.startswith("Bearer "):
                    raise ValueError("Invalid Authorization header")

                token = auth_header.split(" ")[1]

                if not Integration.objects.filter(
                        token=token, name=integration_name
                ).first():
                    raise ValueError("Invalid Authorization header")
                else:
                    result = func(self, request, *args, **kwargs)
                return result
            except Exception as e:
                return CustomResponse(general_message=str(e)).get_failure_response()

        return wrapper

    return decorator


def get_access_token(
        email_or_muid: str = None, password: str = None, token: str = None
) -> dict | None:
    """
    The `get_access_token` function is used to authenticate a user and retrieve an access token and
    refresh token.

    :param email_or_muid: The email or μID of the user for authentication
    :param password: The password parameter is used to provide the user's password for authentication
    :param token: The `token` parameter is used for token verification. If
    provided, the function will make a POST request to the authentication domain with the token to
    verify its validity
    :return: a dictionary with two keys: "accessToken" and "refreshToken".
    """

    auth_domain = decouple.config("AUTH_DOMAIN")

    if password or email_or_muid:
        response = requests.post(
            f"{auth_domain}/api/v1/auth/user-authentication/",
            data={"emailOrMuid": email_or_muid, "password": password},
        )
    else:
        response = requests.post(
            f"{auth_domain}/api/v1/auth/token-verification/{token}/",
        )

    response = response.json()
    if response.get("statusCode") != 200:
        raise ValueError(response.get("message").get("general")[0])

    res_data = response.get("response")
    access_token = res_data.get("accessToken")
    refresh_token = res_data.get("refreshToken")

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
    }
