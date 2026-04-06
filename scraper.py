# coding: utf-8
"""
scraper.py — 商品信息采集模块
==============================
用采集账号登录后，打开指定商品详情/编辑页，提取所有表单字段的：
  - 字段名称（label）
  - 字段 ID（field_id）
  - 控件类型（field_type: select / combobox / input）
  - 当前值（value）

对外接口：
  async def scrape_goods(page, detail_url) -> list[dict]
    返回 [{"field_id": ..., "label": ..., "field_type": ..., "value": ...}, ...]
"""

from playwright.async_api import Page


async def scrape_goods(page: Page, detail_url: str) -> list[dict]:
    """
    采集商品详情/编辑页的所有字段信息。

    参数：
      page       : 已登录的 Playwright Page 对象
      detail_url : 商品详情页或编辑页 URL

    返回：
      list[dict]，每项含 field_id / label / field_type / value
    """
    print(f"  [scraper] 正在打开商品页面: {detail_url}")
    await page.goto(detail_url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)
    await page.wait_for_load_state("domcontentloaded", timeout=20000)
    await page.wait_for_timeout(3000)

    # 全页滚动触发懒加载
    total_height = await page.evaluate("() => document.body.scrollHeight")
    for y in range(0, total_height, 300):
        await page.evaluate(f"window.scrollTo(0, {y})")
        await page.wait_for_timeout(80)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1000)
    print("  [scraper] 页面滚动完成")

    # 提取所有表单字段信息
    fields = await page.evaluate("""
        () => {
            const results = [];

            // ---- 1. doraemon-select 组件（select / combobox） ----
            const selects = document.querySelectorAll('.doraemon-select[id]');
            selects.forEach(el => {
                const fid = el.getAttribute('id');
                if (!fid || /^\\d+$/.test(fid) === false) return;

                // 找对应的 label
                const label = _findLabel(el, fid);

                // 判断是 select 还是 combobox
                const hasSearch = el.querySelector('input.doraemon-select-search__field');
                const fieldType = hasSearch ? 'combobox' : 'select';

                // 获取当前值（多层策略）
                const value = _getSelectValue(el, hasSearch);

                results.push({ field_id: fid, label: label, field_type: fieldType, value: value });
            });

            // ---- 2. 普通 input 文本框 ----
            const inputs = document.querySelectorAll('input[id]');
            inputs.forEach(inp => {
                const fid = inp.getAttribute('id');
                if (!fid || /^\\d+$/.test(fid) === false) return;

                // 跳过已由 doraemon-select 处理的 input
                const parentSelect = inp.closest('.doraemon-select');
                if (parentSelect) return;

                // 跳过搜索框、隐藏输入等
                if (inp.type === 'hidden' || inp.type === 'submit' || inp.type === 'button') return;

                const label = _findLabel(inp, fid);
                const value = (inp.value || '').trim();

                results.push({ field_id: fid, label: label, field_type: 'input', value: value });
            });

            // ---- 3. textarea ----
            const textareas = document.querySelectorAll('textarea[id]');
            textareas.forEach(ta => {
                const fid = ta.getAttribute('id');
                if (!fid || /^\\d+$/.test(fid) === false) return;

                const label = _findLabel(ta, fid);
                const value = (ta.value || '').trim();

                results.push({ field_id: fid, label: label, field_type: 'input', value: value });
            });

            return results;

            // --- 辅助函数 ---

            function _findLabel(el, fid) {
                // 策略1: 查找 for 属性匹配的 label
                const forLabel = document.querySelector(`label[for="${fid}"]`);
                if (forLabel) return (forLabel.textContent || '').trim();

                // 策略2: 向上找表单容器，再找关联 label
                const formItem = el.closest('.el-form-item, .form-item, [class*="form-item"]');
                if (formItem) {
                    const labelEl = formItem.querySelector('.el-form-item__label, .form-label, label, [class*="label"]');
                    if (labelEl) {
                        let text = (labelEl.textContent || '').trim();
                        // 去掉末尾的冒号和星号
                        text = text.replace(/[:\\s：*]+$/, '');
                        if (text) return text;
                    }
                }

                // 策略3: 查找同级的 label 或前一个兄弟元素
                const parent = el.parentElement;
                if (parent) {
                    const prevLabel = parent.querySelector(':scope > label, :scope > .label, :scope > [class*="label"]');
                    if (prevLabel) {
                        let text = (prevLabel.textContent || '').trim();
                        text = text.replace(/[:\\s：*]+$/, '');
                        if (text) return text;
                    }
                }

                return fid;
            }

            function _getSelectValue(el, hasSearch) {
                // 策略1（combobox 优先）: 搜索输入框的 value 就是实际选中/输入值
                if (hasSearch) {
                    const searchInput = el.querySelector('input.doraemon-select-search__field');
                    if (searchInput) {
                        const val = (searchInput.value || '').trim();
                        // 排除 placeholder（通常是"请输入"开头的内容）
                        if (val && !/^请输入/.test(val)) {
                            return val;
                        }
                    }
                }

                // 策略2: 查找选中值的专用 DOM 元素（非 placeholder）
                // doraemon-select-selected-value / selection-selected-value 是选中项的容器
                const selectedValueEl = el.querySelector(
                    '.doraemon-select-selection-selected-value, ' +
                    '.doraemon-select-selected-value, ' +
                    '[class*="selection-selected-value"]'
                );
                if (selectedValueEl) {
                    let text = (selectedValueEl.textContent || '').trim();
                    text = text.replace(/\\s*×\\s*$/, '').trim();
                    if (text && !/^请输入/.test(text)) {
                        return text;
                    }
                }

                // 策略3: selection-rendered 容器中的内容，排除 placeholder
                const rendered = el.querySelector('.doraemon-select-selection-rendered, [class*="selection-rendered"]');
                if (rendered) {
                    // 查找 rendered 内的所有子元素
                    const children = rendered.children;
                    // 优先找 title 属性（选中项通常有 title）
                    for (const child of children) {
                        const title = (child.getAttribute('title') || '').trim();
                        if (title && !/^请输入/.test(title)) {
                            return title;
                        }
                    }
                    // 尝试找非隐藏的文字节点
                    let text = (rendered.textContent || '').trim();
                    text = text.replace(/\\s*×\\s*$/, '').trim();
                    if (text && !/^请输入/.test(text)) {
                        return text;
                    }
                }

                // 策略4: 隐藏 input（antd 的 value 存储方式）
                const hiddenInput = el.querySelector('input[type="hidden"]');
                if (hiddenInput && hiddenInput.value) {
                    return hiddenInput.value.trim();
                }

                // 策略5: data 属性（有些组件用 data-value 存储）
                const dataValue = el.getAttribute('data-value') || '';
                if (dataValue) return dataValue.trim();

                return '';
            }
        }
    """)

    # 过滤掉空值字段（保留有名称或有值的字段）
    filtered = [f for f in fields if f["label"] or f["value"]]
    print(f"  [scraper] 采集完成，共提取 {len(filtered)} 个有效字段")
    for f in filtered:
        print(f"    [{f['label']}]  id={f['field_id']}  type={f['field_type']}  => '{f['value']}'")

    return filtered
