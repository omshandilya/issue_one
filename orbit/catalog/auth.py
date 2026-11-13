"""Who is asking? Analysts send `Authorization: Bearer <token>`."""
from fastapi import Header, HTTPException

# token -> (user name, unit). Test accounts are listed in seed/users.md.
USERS = {
    "tok-analyst-a-7f3c": ("analyst_a", "A"),
    "tok-analyst-b-91d2": ("analyst_b", "B"),
    "tok-viewer-3e55": ("viewer", None),
}


def current_user(authorization: str = Header(default=None)):
    """Returns (name, unit). No header = anonymous. A bad token is rejected."""
    if not authorization:
        return ("anonymous", None)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token not in USERS:
        raise HTTPException(status_code=401, detail="invalid token")
    return USERS[token]


def can_see(unit, restricted_unit):
    return restricted_unit is None or restricted_unit == unit
