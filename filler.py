# coding: utf-8
"""
filler.py — 表单填写核心模块
============================
负责根据字段定义和目标值，向页面的 doraemon 组件填写数据。

【doraemon-select 的 DOM 结构说明】
  <div id="{field_id}" class="doraemon-select ...">
    <div class="doraemon-select-selection" role="combobox">
      ...
      <input class="doraemon-select-search__field">  ← 搜索输入框
    </div>
  </div>
  
  注意：field_id 是外层 div.doraemon-select 容器的 id，不是 input 的 id！

支持的控件类型：
  "input"    : 普通 <input> 文本框（直接 fill）
  "select"   : 纯下拉（点击展开 → 从列表选目标项，不支持直接输入）
  "combobox" : 可输入下拉（输入搜索词 → 从候选列表选，或保留输入值）

对外接口：
  await fill_field(page, field_def, value)
"""

import asyncio
from playwright.async_api import Page


# ------ doraemon-select 操作辅助 ------

async def _scroll_into_view(page: Page, field_id: str):
    """滚动使元素进入视口（触发懒渲染）"""
    await page.evaluate(f"""
        () => {{
            const el = document.getElementById('{field_id}');
            if (el) el.scrollIntoView({{block: 'center', behavior: 'smooth'}});
        }}
    """)
    await page.wait_for_timeout(600)


def _select_locator(page: Page, field_id: str):
    """
    返回 doraemon-select 容器的 Locator。
    注意：CSS id 选择器 #82544 在 id 以数字开头时不合法，
    要使用属性选择器 [id="82544"] 代替。
    """
    return page.locator(f'[id="{field_id}"].doraemon-select').first


async def _ensure_select_exists(page: Page, field_id: str):
    """
    先滚动到元素位置（触发懒渲染），再确认选择器存在。
    最多尝试 3 次，每次等待 1 秒。
    """
    for attempt in range(3):
        await _scroll_into_view(page, field_id)
        sel_loc = _select_locator(page, field_id)
        count = await sel_loc.count()
        if count > 0:
            return sel_loc
        print(f"    [filler] 第 {attempt+1} 次未找到 id='{field_id}'，等待后重试...")
        await page.wait_for_timeout(1000)
    
    raise RuntimeError(
        f"字段 id='{field_id}' 对应的 doraemon-select 容器未找到，"
        "请检查字段 ID 是否正确，或页面是否已完全加载"
    )


async def _open_select(page: Page, select_loc):
    """点击 doraemon-select 容器，打开下拉"""
    await select_loc.click()
    await page.wait_for_timeout(600)


async def _get_dropdown(page: Page, timeout: int = 5000):
    """
    获取当前展开的下拉弹层。
    doraemon 下拉弹层挂在 body 下，class 包含 doraemon-select-dropdown（且不含 hidden）。
    """
    dropdown = page.locator(
        ".doraemon-select-dropdown:not(.doraemon-select-dropdown-hidden)"
    ).last
    try:
        await dropdown.wait_for(state="visible", timeout=timeout)
        return dropdown
    except Exception:
        return None


async def _pick_option(page: Page, value: str) -> bool:
    """
    在展开的下拉列表中选择选项。
    先精确匹配，再模糊匹配。
    返回是否成功选中。
    """
    items = page.locator(
        ".doraemon-select-dropdown:not(.doraemon-select-dropdown-hidden) "
        ".doraemon-select-dropdown-menu-item"
    )
    count = await items.count()

    # 精确匹配
    for i in range(count):
        item = items.nth(i)
        text = (await item.inner_text()).strip()
        if text == value:
            await item.click()
            await page.wait_for_timeout(300)
            print(f"    [filler] 精确选中: '{text}'")
            return True

    # 模糊匹配
    for i in range(count):
        item = items.nth(i)
        text = (await item.inner_text()).strip()
        if value in text or text in value:
            await item.click()
            await page.wait_for_timeout(300)
            print(f"    [filler] 模糊选中: '{text}'（目标: '{value}'）")
            return True

    # 打印所有选项方便排查
    opts = []
    for i in range(min(count, 20)):
        opts.append((await items.nth(i).inner_text()).strip())
    print(f"    [filler] 未找到 '{value}'，候选列表: {opts}")
    return False


async def _close_dropdown(page: Page):
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)


# ------ 三种控件类型 ------

async def _fill_input(page: Page, field_id: str, value: str):
    """普通文本框"""
    inp = page.locator(f"#{field_id}").first
    await inp.wait_for(state="visible", timeout=5000)
    await inp.click()
    await inp.fill("")
    await inp.type(value, delay=80)
    print(f"    [filler] input 已填写: '{value}'")


async def _fill_select(page: Page, field_id: str, value: str):
    """
    纯下拉（select）：
    只能从固定列表中选，不支持直接输入。
    策略：点击展开 → 从列表选目标项。
    """
    await _scroll_into_view(page, field_id)
    select_loc = await _ensure_select_exists(page, field_id)
    await _open_select(page, select_loc)

    dropdown = await _get_dropdown(page)
    if dropdown is None:
        raise RuntimeError(f"字段 '{field_id}' 下拉列表未出现")

    found = await _pick_option(page, value)
    if not found:
        await _close_dropdown(page)
        raise RuntimeError(f"字段 '{field_id}' 下拉列表中没有选项 '{value}'")


async def _fill_combobox(page: Page, field_id: str, value: str):
    """
    可输入下拉（combobox）：
    先输入搜索词 → 等待候选列表 → 选中匹配项。
    若无候选项则直接保留输入内容（自由输入模式）。
    """
    await _scroll_into_view(page, field_id)
    select_loc = await _ensure_select_exists(page, field_id)

    # 找 combobox 内部的搜索输入框
    search_input = select_loc.locator("input.doraemon-select-search__field").first
    await search_input.wait_for(state="visible", timeout=5000)

    # 先点击展开，再输入
    await select_loc.click()
    await page.wait_for_timeout(300)
    await search_input.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Delete")
    await search_input.type(value, delay=100)
    await page.wait_for_timeout(800)  # 等候选列表刷新

    dropdown = await _get_dropdown(page, timeout=3000)
    if dropdown is not None:
        found = await _pick_option(page, value)
        if not found:
            # 无匹配候选 → 输入值本身就是答案（自由输入）
            await _close_dropdown(page)
            # 验证输入值是否保留
            current = await search_input.input_value()
            print(f"    [filler] 无候选匹配，保留输入值: '{current}'")
    else:
        print(f"    [filler] 无下拉列表，输入值保留: '{value}'")


# ------ 对外主接口 ------

async def fill_field(page: Page, field_def: dict, value: str):
    """
    填写单个字段。

    参数：
      page      : Playwright Page 对象
      field_def : fields.py 中字段描述 dict（含 field_id、label、field_type）
      value     : 要填入的字符串值
    """
    field_id   = field_def["field_id"]
    label      = field_def["label"]
    field_type = field_def["field_type"]

    print(f"  [filler] 填写 [{label}] (id={field_id}, type={field_type}) => '{value}'")

    if field_type == "input":
        await _fill_input(page, field_id, value)
    elif field_type == "select":
        await _fill_select(page, field_id, value)
    elif field_type == "combobox":
        await _fill_combobox(page, field_id, value)
    else:
        raise ValueError(f"未知 field_type: '{field_type}'")

    print(f"  [filler] [{label}] 填写完成")
