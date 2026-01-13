"""JWT authentication stub for development.

TODO: Implement proper JWT authentication with user management.
"""


async def get_current_active_user() -> dict:
    """Stub function that returns a default user for development.

    TODO: Replace with proper JWT token validation and user lookup.
    """
    return {
        "id": 1,
        "user_id": 1,  # Added for compatibility
        "email": "dev@example.com",
        "username": "dev",
        "is_active": True,
    }
