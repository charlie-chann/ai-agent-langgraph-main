# tools/rbac.py — Role-Based Access Control for enterprise tools
from config import ROLES
from loguru import logger


def get_user_role(username: str) -> str:
    """Look up a user's role. In production, query LDAP/Active Directory."""
    # Mock mapping — replace with real directory lookup
    _USER_ROLES = {
        "admin_user":    "admin",
        "mgr_alice":     "manager",
        "mgr_bob":       "manager",
        "emp_charlie":   "employee",
        "emp_diana":     "employee",
        "emp_eve":       "employee",
    }
    return _USER_ROLES.get(username, "employee")  # default to employee


def check_permission(username: str, action: str) -> tuple[bool, str]:
    """
    Check if user has permission for an action.
    Returns: (allowed: bool, reason: str)
    """
    role = get_user_role(username)
    allowed_actions = ROLES.get(role, ROLES["guest"])["can"]
    if action in allowed_actions:
        logger.debug(f"[RBAC] {username}({role}) ✓ {action}")
        return True, f"Allowed ({role})"
    logger.warning(f"[RBAC] {username}({role}) ✗ {action}")
    return False, f"Permission denied: role '{role}' cannot perform '{action}'"


def get_allowed_tools(username: str) -> list[str]:
    """Return list of tool names this user can access."""
    role = get_user_role(username)
    return ROLES.get(role, ROLES["guest"])["can"]
