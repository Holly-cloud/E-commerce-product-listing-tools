# coding: utf-8
"""
config.py — 全局配置
====================
把所有"容易变动"的内容集中在这里：账号、密码、目标URL。
修改时只需改这个文件，其他模块不用动。
"""

# -------- 账号信息 --------
# 发布账号（用于自动填写商品发布页）
USERNAME = "cykj1314"
PASSWORD = "Nxkj18607072433!"

# 采集账号（用于采集其他账号的商品信息，用于一键复制发布）
SCRAPER_USERNAME = "ffdn1314"
SCRAPER_PASSWORD = "Nxkj18607072433!"

# -------- 目标页面 --------
TARGET_URL = (
    "https://www.jxemall.com/goods-center/goods/publish"
    "?categoryId=5162"
    "&protocolId=1401000000157458"
    "&bidId=11777"
    "&instanceCode=JXWSCS"
    "&spuId=101779275"
)

# -------- 浏览器选项 --------
HEADLESS = False        # True=无界面后台运行；False=显示浏览器窗口（调试时用）
SLOW_MO = 150           # 每步操作之间的延迟（毫秒），调高可以让操作更稳定
VIEWPORT = {"width": 1440, "height": 900}
