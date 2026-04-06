# coding: utf-8
"""
accounts.py — 账户本管理
========================
用 JSON 文件持久化存储多个账号密码，支持：
  - 增删改查账号
  - 设置默认发布账号 / 默认采集账号
  - 首次运行时自动从 config.py 导入默认账号

数据文件：autofill/accounts.json
格式：
  [
    {"name": "发布账号A", "username": "xxx", "password": "yyy", "is_default_publish": true},
    {"name": "采集账号B", "username": "aaa", "password": "bbb", "is_default_scrape": true},
  ]
"""

import json
import os
import sys

# ── 文件路径 ──
_ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")


def _load_accounts() -> list[dict]:
    """从 JSON 文件加载账户列表"""
    if not os.path.exists(_ACCOUNTS_FILE):
        return []
    try:
        with open(_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 基本校验
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, IOError):
        return []


def _save_accounts(accounts: list[dict]):
    """将账户列表保存到 JSON 文件"""
    with open(_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def init_accounts():
    """
    初始化账户本。
    如果 JSON 文件不存在，从 config.py 导入两个默认账号。
    返回账户列表。
    """
    accounts = _load_accounts()
    if accounts:
        return accounts

    # 首次运行：从 config.py 导入
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from autofill.config import USERNAME, PASSWORD, SCRAPER_USERNAME, SCRAPER_PASSWORD
        accounts = [
            {
                "name": "发布账号",
                "username": USERNAME,
                "password": PASSWORD,
                "is_default_publish": True,
                "is_default_scrape": False,
            },
            {
                "name": "采集账号",
                "username": SCRAPER_USERNAME,
                "password": SCRAPER_PASSWORD,
                "is_default_publish": False,
                "is_default_scrape": True,
            },
        ]
        _save_accounts(accounts)
    except ImportError:
        pass

    return accounts


def get_accounts() -> list[dict]:
    """获取所有账户（列表的深拷贝）"""
    import copy
    return copy.deepcopy(_load_accounts())


def add_account(name: str, username: str, password: str,
                is_default_publish: bool = False,
                is_default_scrape: bool = False) -> list[dict]:
    """
    新增账号。
    返回更新后的完整账户列表。
    """
    accounts = _load_accounts()
    accounts.append({
        "name": name,
        "username": username,
        "password": password,
        "is_default_publish": is_default_publish,
        "is_default_scrape": is_default_scrape,
    })
    _save_accounts(accounts)
    return accounts


def delete_account(index: int) -> list[dict]:
    """
    删除指定索引的账号。
    返回更新后的完整账户列表。
    """
    accounts = _load_accounts()
    if 0 <= index < len(accounts):
        accounts.pop(index)
        _save_accounts(accounts)
    return accounts


def update_account(index: int, name: str = None, username: str = None,
                   password: str = None) -> list[dict]:
    """
    更新指定索引的账号信息。
    只更新非 None 的字段。
    返回更新后的完整账户列表。
    """
    accounts = _load_accounts()
    if 0 <= index < len(accounts):
        if name is not None:
            accounts[index]["name"] = name
        if username is not None:
            accounts[index]["username"] = username
        if password is not None:
            accounts[index]["password"] = password
        _save_accounts(accounts)
    return accounts


def set_default(index: int, role: str) -> list[dict]:
    """
    将指定索引的账号设为默认。
    role: "publish" 或 "scrape"
    返回更新后的完整账户列表。
    """
    accounts = _load_accounts()
    key = f"is_default_{role}"
    if 0 <= index < len(accounts):
        # 先清除所有该角色的默认标记
        for acc in accounts:
            acc[key] = False
        # 设置新的默认
        accounts[index][key] = True
        _save_accounts(accounts)
    return accounts


def get_default(role: str) -> dict | None:
    """
    获取指定角色的默认账号。
    role: "publish" 或 "scrape"
    返回账号 dict 或 None。
    """
    accounts = _load_accounts()
    key = f"is_default_{role}"
    for acc in accounts:
        if acc.get(key):
            return acc
    return None
