# coding: utf-8
"""
fields.py — 字段定义表
======================
每个字段对应页面上的一个表单控件。

字段描述格式（dict）：
  field_id    : 字段的唯一 ID（与页面 input 的 id 属性一致）
  label       : 字段的中文名（仅用于日志，不影响操作）
  field_type  : 控件类型，决定填写逻辑：
                  "select"   — 纯下拉（点击展开 → 从列表选）
                  "combobox" — 可输入的下拉（输入文字 → 等待列表 → 选第一项或匹配项）
                  "input"    — 普通文本输入框

如何扩展新字段：
  1. 在 FIELD_DEFINITIONS 列表末尾添加一个新的 dict。
  2. field_id 填写页面 <input> 元素的 id 属性值（在浏览器开发者工具里查）。
  3. field_type 根据控件类型填写 "select" / "combobox" / "input"。
  4. 在 autofill.py 的 FILL_DATA 里添加对应的键值对。
  完成！不需要改其他任何文件。
"""

FIELD_DEFINITIONS = []

# 用 field_id 作为 key 方便快速查找
FIELDS_BY_ID = {f["field_id"]: f for f in FIELD_DEFINITIONS}
