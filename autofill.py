# coding: utf-8
"""
autofill.py — 主入口
=====================
在这里填写商品信息，然后运行此脚本即可自动完成填写。

【使用方法】
  1. 修改下方 FILL_DATA，填入本次商品的各字段值
  2. 在命令行运行：
       python autofill/autofill.py
  3. 浏览器会自动打开、登录、填写，完成后保持打开供检查

【添加新字段】
  1. 在 fields.py 的 FIELD_DEFINITIONS 列表里添加字段定义
  2. 在本文件的 FILL_DATA 里添加对应 field_id 和值
  详见 fields.py 的注释说明。
"""

import asyncio
import sys
import os

# 让脚本无论从哪个目录运行都能正确 import autofill 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from autofill.config import USERNAME, PASSWORD, TARGET_URL, HEADLESS, SLOW_MO, VIEWPORT
from autofill.login import ensure_logged_in
from autofill.filler import fill_field
from autofill.fields import FIELDS_BY_ID, FIELD_DEFINITIONS


# ================================================================
# 填写数据 — 每次使用时修改这里
# key   : 字段 ID（与 fields.py 中 field_id 一致）
# value : 要填写的值
# ================================================================
FILL_DATA = {
    "82544":   "盒",       # 计量单位
    "1502406": "格之格",   # 制造商名称
    "1502407": "中",       # 制造商规模
    "82546":   "格之格",   # 生产厂商
}
# ================================================================


async def run_autofill():
    """执行完整的自动填写流程"""

    print("=" * 50)
    print("商品信息自动填写工具 v1.0")
    print("=" * 50)
    print(f"目标页面: {TARGET_URL}")
    print(f"待填写字段 ({len(FILL_DATA)} 项):")
    for fid, val in FILL_DATA.items():
        fd = FIELDS_BY_ID.get(fid)
        label = fd["label"] if fd else fid
        print(f"  [{label}]: {val}")
    print("-" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            slow_mo=SLOW_MO,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport=VIEWPORT,
            locale="zh-CN",
        )
        page = await context.new_page()

        # ---- 1. 导航到目标页 ----
        print("\n[步骤 1] 打开目标页面...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)

        # ---- 2. 登录 ----
        print("\n[步骤 2] 检查登录状态...")
        await ensure_logged_in(page, USERNAME, PASSWORD)

        # ---- 3. 确认到达发布页 ----
        if "goods/publish" not in page.url and "goods-center" not in page.url:
            print(f"\n[步骤 3] 登录后重新导航到发布页...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

        # 等待页面主内容加载（SPA 不用等 networkidle，直接等固定时间）
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await page.wait_for_timeout(5000)   # SPA 渲染需要足够时间
        print(f"\n[步骤 3] 已到达发布页: {page.url}")

        # ---- 4. 慢速全页滚动，触发懒加载渲染 ----
        print("\n[步骤 4] 滚动页面触发懒加载渲染...")
        total_height = await page.evaluate("() => document.body.scrollHeight")
        for y in range(0, total_height, 300):
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_timeout(100)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1500)   # 滚回顶部后等待稳定
        print("  页面滚动完成，所有内容已渲染")

        # ---- 5. 逐一填写字段 ----
        print("\n[步骤 5] 开始填写字段...")
        errors = []
        for field_def in FIELD_DEFINITIONS:
            fid = field_def["field_id"]
            if fid not in FILL_DATA:
                continue  # 本次不填写此字段，跳过
            value = FILL_DATA[fid]

            try:
                await fill_field(page, field_def, value)
                await page.wait_for_timeout(300)
            except Exception as e:
                errors.append((field_def["label"], str(e)))

        # ---- 5. 结果汇报 ----
        print("\n" + "=" * 50)
        if not errors:
            print("所有字段填写完成！")
        else:
            print(f"填写完成，但有 {len(errors)} 个字段失败：")
            for label, msg in errors:
                print(f"  [{label}] 错误: {msg}")
        print("=" * 50)
        print("\n浏览器将保持打开，请手动检查页面填写结果。")
        print("（检查完毕后请手动关闭浏览器窗口）")


if __name__ == "__main__":
    # Windows 需要设置编码避免 GBK 问题
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    asyncio.run(run_autofill())
