"""
tools/rbac.py — 基于角色的访问控制（RBAC）模块

【职责】
根据用户名解析角色，校验用户是否具备执行某项操作的权限，
并返回该用户可调用的工具名称列表。

【设计原因】
企业内网场景要求不同职级只能访问对应能力（如普通员工不能关单、发通知）。
将权限逻辑集中在本模块，Agent 与 API 层统一调用，便于日后替换为 LDAP/AD 查询。
"""
from config import ROLES
from loguru import logger


def get_user_role(username: str) -> str:
    """
    根据用户名查询其角色。

    生产环境应查询 LDAP/Active Directory；当前为演示用的内存映射表。

    Args:
        username: 企业域账号或邮箱前缀

    Returns:
        角色标识字符串，如 admin / manager / employee / guest
    """
    # 演示用静态映射 — 上线后替换为真实目录服务查询
    _USER_ROLES = {
        "admin_user":    "admin",
        "mgr_alice":     "manager",
        "mgr_bob":       "manager",
        "emp_charlie":   "employee",
        "emp_diana":     "employee",
        "emp_eve":       "employee",
    }
    return _USER_ROLES.get(username, "employee")  # 未知用户默认赋予 employee 角色


def check_permission(username: str, action: str) -> tuple[bool, str]:
    """
    校验用户是否有权执行指定操作。

    Args:
        username: 当前操作用户名
        action: 待校验的动作名，须与 config.ROLES 中 can 列表项一致

    Returns:
        (allowed, reason) 元组：allowed 为 True 表示允许；reason 为可读说明
    """
    role = get_user_role(username)
    allowed_actions = ROLES.get(role, ROLES["guest"])["can"]
    if action in allowed_actions:
        logger.debug(f"[RBAC] {username}({role}) ✓ {action}")
        return True, f"Allowed ({role})"
    logger.warning(f"[RBAC] {username}({role}) ✗ {action}")
    return False, f"Permission denied: role '{role}' cannot perform '{action}'"


def get_allowed_tools(username: str) -> list[str]:
    """
    返回当前用户可调用的全部工具名称列表。

    Args:
        username: 当前用户账号

    Returns:
        与 LangChain @tool 函数 name 对应的字符串列表
    """
    role = get_user_role(username)
    return ROLES.get(role, ROLES["guest"])["can"]
