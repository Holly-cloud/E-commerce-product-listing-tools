# coding: utf-8
"""
launcher.py — 打包版启动器
==========================
在 PyInstaller 打包环境中，将 PLAYWRIGHT_BROWSERS_PATH 指向
程序自带的 _browser 目录，使 Playwright 能找到 Chromium。

此文件仅在打包环境中生效。
"""

import os
import sys


def setup_browser_path():
    """设置 Playwright 浏览器路径为程序自带目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的目录
        base_dir = os.path.dirname(sys.executable)
        browser_dir = os.path.join(base_dir, '_browser')
        if os.path.isdir(browser_dir):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browser_dir
            print(f"[启动器] 浏览器路径: {browser_dir}")


if __name__ == '__main__':
    setup_browser_path()

    # 导入并启动 GUI
    sys.path.insert(0, os.path.dirname(sys.executable))
    from autofill.gui import main
    main()
