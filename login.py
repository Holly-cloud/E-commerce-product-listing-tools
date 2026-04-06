# coding: utf-8
"""
login.py — 登录模块
====================
负责：自动识别登录页 → 切换"账号登录"tab → 填写账号密码 → 点击登录 → 等待跳转成功。

对外接口：
  await ensure_logged_in(page)
    - 如果当前在登录页，执行完整登录流程
    - 如果已经登录（不在登录页），直接返回
    - 登录失败时抛出 RuntimeError
"""

import asyncio
from playwright.async_api import Page


# ------ 内部常量（选择器） ------
_ACCOUNT_TAB_SELECTOR = "span.login-type:has-text('账号登录')"
_USERNAME_SELECTOR    = "input[name='username']"
_PASSWORD_SELECTOR    = "input[name='password']"
_LOGIN_BTN_SELECTOR   = "[class*='login-btn']"


def _is_on_login_page(url: str) -> bool:
    return "login" in url


async def _switch_to_account_tab(page: Page):
    """切换到"账号登录"标签页（而非默认的 CA 登录）"""
    try:
        tab = page.locator(_ACCOUNT_TAB_SELECTOR).first
        await tab.wait_for(state="visible", timeout=5000)
        await tab.click()
        await page.wait_for_timeout(1000)
        print("  [login] 已切换到账号登录 tab")
    except Exception as e:
        raise RuntimeError(f"未找到账号登录 tab: {e}")


async def _fill_credentials(page: Page, username: str, password: str):
    """填写账号和密码"""
    # 填账号
    inp_user = page.locator(_USERNAME_SELECTOR).first
    await inp_user.wait_for(state="visible", timeout=5000)
    await inp_user.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await page.wait_for_timeout(100)
    await inp_user.type(username, delay=80)

    # 验证填写结果
    actual = await inp_user.input_value()
    if actual != username:
        raise RuntimeError(f"账号填写异常：期望 '{username}'，实际 '{actual}'")
    print(f"  [login] 账号填写: {actual}")

    # 填密码
    inp_pwd = page.locator(_PASSWORD_SELECTOR).first
    await inp_pwd.wait_for(state="visible", timeout=5000)
    await inp_pwd.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await page.wait_for_timeout(100)
    await inp_pwd.type(password, delay=80)
    print("  [login] 密码已填写")


async def _click_login_button(page: Page):
    """点击登录按钮"""
    btn = page.locator(_LOGIN_BTN_SELECTOR).first
    await btn.wait_for(state="visible", timeout=5000)
    await btn.click()
    print("  [login] 已点击登录按钮")


async def _wait_for_login_success(page: Page, timeout: int = 20000):
    """等待页面跳转离开登录页，超时则报错"""
    try:
        await page.wait_for_url(
            lambda url: "login" not in url,
            timeout=timeout
        )
        print(f"  [login] 登录成功，跳转到: {page.url}")
    except Exception:
        # 尝试读取页面错误提示
        err_msg = await page.evaluate("""
            () => {
                const nodes = document.querySelectorAll(
                    '[class*="error"], [class*="alert"], [class*="tip"], [class*="msg"]'
                );
                return Array.from(nodes)
                    .map(n => n.textContent.trim())
                    .filter(t => t && t.length < 100)
                    .join(' | ');
            }
        """)
        hint = f"（页面提示：{err_msg}）" if err_msg else ""
        raise RuntimeError(f"登录超时，未能跳转离开登录页 {hint}")


async def ensure_logged_in(page: Page, username: str, password: str):
    """
    确保已登录。
    - 若在登录页：执行完整登录流程
    - 若已在其他页面：直接返回（假设已登录）
    - 登录失败：抛出 RuntimeError
    """
    await page.wait_for_load_state("networkidle", timeout=20000)

    if not _is_on_login_page(page.url):
        print("  [login] 已登录，无需重新登录")
        return

    print(f"  [login] 检测到登录页: {page.url}")
    await _switch_to_account_tab(page)
    await _fill_credentials(page, username, password)
    await _click_login_button(page)
    await _wait_for_login_success(page)
