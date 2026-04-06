# coding: utf-8
"""
gui.py — 图形化界面入口
========================
使用 Python 内置的 tkinter，无需额外安装依赖。

界面功能：
  1. 账户管理：下拉切换发布/采集账号，支持添加/删除
  2. 字段表：显示当前所有字段，可直接编辑"填写值"
  3. 新增字段：填写字段 ID / 名称 / 类型 → 点"添加"即可
  4. 删除字段：选中行 → 点"删除选中行"
  5. 运行：点"开始填写"启动自动化，实时日志输出到界面底部
  6. 字段变动后可选择"保存到 fields.py"（持久化）
  7. 采集：输入商品详情页链接 → 一键采集字段信息 → 自动填入字段表

运行方式：
  python autofill/gui.py
"""

import sys
import os
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# 让脚本无论从哪里运行都能 import autofill 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autofill.config import TARGET_URL
from autofill import accounts as acc_module
import autofill.fields as fields_module
from autofill.fields import FIELD_DEFINITIONS, FIELDS_BY_ID


# ─────────────────────────────────────────────
# 字段类型选项
# ─────────────────────────────────────────────
FIELD_TYPES = ["select", "combobox", "input"]


# ─────────────────────────────────────────────
# 持久化：把当前字段列表写回 fields.py
# ─────────────────────────────────────────────
def save_fields_to_file(field_rows: list[dict]):
    """
    将 field_rows 列表写回 autofill/fields.py。
    field_rows 每项: {"field_id": str, "label": str, "field_type": str, "value": str}
    """
    fields_path = os.path.join(os.path.dirname(__file__), "fields.py")

    lines = [
        "# coding: utf-8\n",
        '"""\n',
        "fields.py - 字段定义表\n",
        "======================\n",
        "每个字段对应页面上的一个表单控件。\n",
        "\n",
        "字段描述格式（dict）：\n",
        "  field_id    : 字段的唯一 ID（与页面 input 的 id 属性一致）\n",
        "  label       : 字段的中文名（仅用于日志，不影响操作）\n",
        "  field_type  : 控件类型，决定填写逻辑：\n",
        '                  "select"   - 纯下拉（点击展开 -> 从列表选）\n',
        '                  "combobox" - 可输入的下拉（输入文字 -> 等待列表 -> 选第一项或匹配项）\n',
        '                  "input"    - 普通文本输入框\n',
        '"""\n',
        "\n",
        "FIELD_DEFINITIONS = [\n",
    ]
    for row in field_rows:
        lines.append("    {\n")
        lines.append(f'        "field_id":   "{row["field_id"]}",\n')
        lines.append(f'        "label":      "{row["label"]}",\n')
        lines.append(f'        "field_type": "{row["field_type"]}",\n')
        lines.append("    },\n")
    lines.append("]\n")
    lines.append("\n")
    lines.append("# 用 field_id 作为 key 方便快速查找\n")
    lines.append("FIELDS_BY_ID = {f[\"field_id\"]: f for f in FIELD_DEFINITIONS}\n")

    with open(fields_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ─────────────────────────────────────────────
# 主界面
# ─────────────────────────────────────────────
class AutofillGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("上架工具")
        self.root.geometry("960x850")
        self.root.resizable(True, True)
        self.root.configure(bg="#f5f5f5")

        # 内部数据：每项 {"field_id", "label", "field_type", "value"}
        self._rows: list[dict] = []
        self._load_initial_rows()

        # 账户本数据
        self._accounts = acc_module.init_accounts()

        self._build_ui()
        self._refresh_account_combos()

    # ── 初始化数据 ──
    def _load_initial_rows(self):
        """从 fields.py 的 FIELD_DEFINITIONS 加载初始行，值默认空"""
        self._rows = [
            {
                "field_id":   f["field_id"],
                "label":      f["label"],
                "field_type": f["field_type"],
                "value":      "",
            }
            for f in FIELD_DEFINITIONS
        ]

    # ── 构建界面 ──
    def _build_ui(self):
        # ── 标题栏 ──
        title_frame = tk.Frame(self.root, bg="#1a73e8", pady=8)
        title_frame.pack(fill="x")
        tk.Label(
            title_frame, text="上架工具",
            font=("微软雅黑", 16, "bold"), fg="white", bg="#1a73e8"
        ).pack()

        # ── 账户管理区 ──
        acct_frame = tk.LabelFrame(
            self.root, text="  账户管理  ",
            font=("微软雅黑", 10, "bold"), bg="#f5f5f5",
            padx=8, pady=8
        )
        acct_frame.pack(fill="x", padx=12, pady=(10, 4))
        self._build_account_area(acct_frame)

        # ── 采集功能区 ──
        scrape_frame = tk.LabelFrame(
            self.root, text="  链接设置  ",
            font=("微软雅黑", 10, "bold"), bg="#f5f5f5",
            padx=8, pady=8
        )
        scrape_frame.pack(fill="x", padx=12, pady=(4, 4))
        self._build_scrape_area(scrape_frame)

        # ── 字段表区 ──
        table_frame = tk.LabelFrame(
            self.root, text="  填写字段  ",
            font=("微软雅黑", 10, "bold"), bg="#f5f5f5",
            padx=8, pady=6
        )
        table_frame.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        self._build_table(table_frame)

        # ── 新增字段行 ──
        add_frame = tk.LabelFrame(
            self.root, text="  新增字段  ",
            font=("微软雅黑", 10, "bold"), bg="#f5f5f5",
            padx=8, pady=6
        )
        add_frame.pack(fill="x", padx=12, pady=4)
        self._build_add_row(add_frame)

        # ── 底部按钮 + 日志 ──
        btn_frame = tk.Frame(self.root, bg="#f5f5f5")
        btn_frame.pack(fill="x", padx=12, pady=(4, 2))
        self._build_buttons(btn_frame)

        log_frame = tk.LabelFrame(
            self.root, text="  运行日志  ",
            font=("微软雅黑", 10, "bold"), bg="#f5f5f5",
            padx=8, pady=4
        )
        log_frame.pack(fill="both", expand=False, padx=12, pady=(2, 10))
        self._build_log(log_frame)

    # ── 账户管理区 ──
    def _build_account_area(self, parent):
        """构建账户管理区域：发布账号下拉 + 采集账号下拉 + 管理按钮"""
        bg = "#f5f5f5"

        # 第一行：发布账号 + 采集账号 下拉
        row1 = tk.Frame(parent, bg=bg)
        row1.pack(fill="x", pady=(0, 6))

        # 发布账号
        tk.Label(row1, text="发布账号：", font=("微软雅黑", 10, "bold"),
                 bg=bg, fg="#1a73e8").pack(side="left")
        self._publish_combo_var = tk.StringVar()
        self._publish_combo = ttk.Combobox(
            row1, textvariable=self._publish_combo_var,
            state="readonly", width=28, font=("微软雅黑", 10)
        )
        self._publish_combo.pack(side="left", padx=(0, 20))
        self._publish_combo.bind("<<ComboboxSelected>>", self._on_publish_combo_change)

        # 采集账号
        tk.Label(row1, text="采集账号：", font=("微软雅黑", 10, "bold"),
                 bg=bg, fg="#7b1fa2").pack(side="left")
        self._scrape_combo_var = tk.StringVar()
        self._scrape_combo = ttk.Combobox(
            row1, textvariable=self._scrape_combo_var,
            state="readonly", width=28, font=("微软雅黑", 10)
        )
        self._scrape_combo.pack(side="left", padx=(0, 12))
        self._scrape_combo.bind("<<ComboboxSelected>>", self._on_scrape_combo_change)

        # 第二行：添加账号 + 管理按钮
        row2 = tk.Frame(parent, bg=bg)
        row2.pack(fill="x")

        tk.Button(
            row2, text="+ 添加账号", font=("微软雅黑", 9),
            bg="#34a853", fg="white", relief="flat", cursor="hand2", padx=8, pady=3,
            command=self._add_account
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            row2, text="删除选中账号", font=("微软雅黑", 9),
            bg="#ea4335", fg="white", relief="flat", cursor="hand2", padx=8, pady=3,
            command=self._delete_account
        ).pack(side="left", padx=(0, 6))

        # 账户详情标签
        self._acct_info_var = tk.StringVar(value="")
        tk.Label(
            row2, textvariable=self._acct_info_var,
            font=("微软雅黑", 8), bg=bg, fg="#666"
        ).pack(side="right")

    def _get_account_display(self, acc: dict) -> str:
        """生成账户在下拉框中的显示文本"""
        label = acc.get("name", acc["username"])
        parts = [label, f"({acc['username']})"]
        if acc.get("is_default_publish"):
            parts.append("[发布]")
        if acc.get("is_default_scrape"):
            parts.append("[采集]")
        return " ".join(parts)

    def _refresh_account_combos(self):
        """刷新两个下拉框的选项，并选中默认项"""
        self._accounts = acc_module.get_accounts()
        display_list = [self._get_account_display(a) for a in self._accounts]

        # 发布账号下拉
        self._publish_combo["values"] = display_list
        default_pub = next((i for i, a in enumerate(self._accounts) if a.get("is_default_publish")), 0)
        if display_list:
            self._publish_combo.current(default_pub)

        # 采集账号下拉
        self._scrape_combo["values"] = display_list
        default_scrape = next((i for i, a in enumerate(self._accounts) if a.get("is_default_scrape")), 0)
        if display_list:
            self._scrape_combo.current(default_scrape)

        self._update_acct_info()

    def _get_selected_publish(self) -> dict | None:
        """获取当前选中的发布账号"""
        idx = self._publish_combo.current()
        if 0 <= idx < len(self._accounts):
            return self._accounts[idx]
        return None

    def _get_selected_scrape(self) -> dict | None:
        """获取当前选中的采集账号"""
        idx = self._scrape_combo.current()
        if 0 <= idx < len(self._accounts):
            return self._accounts[idx]
        return None

    def _on_publish_combo_change(self, _event=None):
        self._update_acct_info()

    def _on_scrape_combo_change(self, _event=None):
        self._update_acct_info()

    def _update_acct_info(self):
        """更新右下角的账号详情提示"""
        pub = self._get_selected_publish()
        scrape = self._get_selected_scrape()
        if pub and scrape:
            self._acct_info_var.set(f"发布: {pub['username']}  |  采集: {scrape['username']}")
        elif pub:
            self._acct_info_var.set(f"发布: {pub['username']}")
        elif scrape:
            self._acct_info_var.set(f"采集: {scrape['username']}")
        else:
            self._acct_info_var.set("")

    def _add_account(self):
        """弹出对话框添加新账号"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加账号")
        dialog.geometry("360x220")
        dialog.resizable(False, False)
        dialog.configure(bg="#f5f5f5")
        dialog.transient(self.root)
        dialog.grab_set()

        bg = "#f5f5f5"
        tk.Label(dialog, text="账号名称：", font=("微软雅黑", 10), bg=bg).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        name_var = tk.StringVar()
        tk.Entry(dialog, textvariable=name_var, width=24, font=("微软雅黑", 10)).grid(row=0, column=1, padx=(0, 12), pady=(12, 4))

        tk.Label(dialog, text="用户名：", font=("微软雅黑", 10), bg=bg).grid(row=1, column=0, sticky="w", padx=12, pady=4)
        user_var = tk.StringVar()
        tk.Entry(dialog, textvariable=user_var, width=24, font=("微软雅黑", 10)).grid(row=1, column=1, padx=(0, 12), pady=4)

        tk.Label(dialog, text="密码：", font=("微软雅黑", 10), bg=bg).grid(row=2, column=0, sticky="w", padx=12, pady=4)
        pwd_var = tk.StringVar()
        tk.Entry(dialog, textvariable=pwd_var, width=24, font=("微软雅黑", 10), show="*").grid(row=2, column=1, padx=(0, 12), pady=4)

        def do_add():
            name = name_var.get().strip()
            username = user_var.get().strip()
            password = pwd_var.get().strip()
            if not username:
                messagebox.showwarning("提示", "用户名不能为空", parent=dialog)
                return
            if not password:
                messagebox.showwarning("提示", "密码不能为空", parent=dialog)
                return
            if not name:
                name = username
            acc_module.add_account(name, username, password)
            self._refresh_account_combos()
            dialog.destroy()
            self._log(f"已添加账号：{name}（{username}）")

        tk.Button(
            dialog, text="确认添加", font=("微软雅黑", 10, "bold"),
            bg="#34a853", fg="white", relief="flat", cursor="hand2", padx=16, pady=4,
            command=do_add
        ).grid(row=3, column=0, columnspan=2, pady=(12, 0))

    def _delete_account(self):
        """删除当前在发布下拉框中选中的账号"""
        idx = self._publish_combo.current()
        if idx < 0 or idx >= len(self._accounts):
            messagebox.showinfo("提示", "请先在发布账号下拉框中选中要删除的账号")
            return
        acc = self._accounts[idx]
        name = acc.get("name", acc["username"])
        if messagebox.askyesno("确认删除", f"确认删除账号 [{name}]（{acc['username']}）？\n\n此操作不可撤销。"):
            acc_module.delete_account(idx)
            self._refresh_account_combos()
            self._log(f"已删除账号：{name}（{acc['username']}）")

    # ── 链接设置区 ──
    def _build_scrape_area(self, parent):
        """链接设置区域：填写目标链接 + 采集商品链接"""
        bg = "#f5f5f5"

        # 第一行：填写目标链接
        row1 = tk.Frame(parent, bg=bg)
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(
            row1, text="填写目标链接：",
            font=("微软雅黑", 10, "bold"), bg=bg, fg="#1a73e8"
        ).pack(side="left")

        self._fill_url_var = tk.StringVar(value=TARGET_URL)
        fill_entry = tk.Entry(
            row1, textvariable=self._fill_url_var,
            font=("Consolas", 10), width=68
        )
        fill_entry.pack(side="left", padx=(0, 6), fill="x", expand=True)

        # 第二行：采集商品信息
        row2 = tk.Frame(parent, bg=bg)
        row2.pack(fill="x")

        tk.Label(
            row2, text="采集商品链接：",
            font=("微软雅黑", 10), bg=bg
        ).pack(side="left")

        self._scrape_url_var = tk.StringVar(value="https://www.jxemall.com/goods-center/goods/edit?categoryId=4629&channelItemId=3039061570270921&btnType=NO_BACK")
        scrape_entry = tk.Entry(
            row2, textvariable=self._scrape_url_var,
            font=("微软雅黑", 10), width=58
        )
        scrape_entry.pack(side="left", padx=(0, 10), fill="x", expand=True)

        tk.Button(
            row2, text="采集并导入字段",
            font=("微软雅黑", 10, "bold"), bg="#7b1fa2", fg="white",
            relief="flat", cursor="hand2", padx=12, pady=4,
            command=self._run_scrape
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            row2, text="清空字段表",
            font=("微软雅黑", 10), bg="#9e9e9e", fg="white",
            relief="flat", cursor="hand2", padx=10, pady=4,
            command=self._clear_all_rows
        ).pack(side="left")

    def _build_table(self, parent):
        """构建字段 Treeview 表格"""
        cols = ("label", "field_id", "field_type", "value")
        col_names = ("字段名称", "字段 ID", "控件类型", "填写值（双击编辑）")
        col_widths = (120, 90, 100, 320)

        # 滚动条
        vsb = ttk.Scrollbar(parent, orient="vertical")
        vsb.pack(side="right", fill="y")

        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=26, font=("微软雅黑", 10))
        style.configure("Custom.Treeview.Heading", font=("微软雅黑", 10, "bold"))

        self.tree = ttk.Treeview(
            parent, columns=cols, show="headings",
            yscrollcommand=vsb.set, style="Custom.Treeview",
            selectmode="browse", height=8
        )
        vsb.config(command=self.tree.yview)

        for col, name, width in zip(cols, col_names, col_widths):
            self.tree.heading(col, text=name)
            self.tree.column(col, width=width, minwidth=60, anchor="w")

        self.tree.pack(fill="both", expand=True)

        # 双击编辑"填写值"
        self.tree.bind("<Double-1>", self._on_double_click)

        # 刷新表格
        self._refresh_table()

    def _build_add_row(self, parent):
        """新增字段的输入行"""
        bg = "#f5f5f5"
        tk.Label(parent, text="字段 ID：", font=("微软雅黑", 10), bg=bg).grid(row=0, column=0, sticky="w")
        self._add_id_var = tk.StringVar()
        tk.Entry(parent, textvariable=self._add_id_var, width=12, font=("微软雅黑", 10)).grid(row=0, column=1, padx=(0, 12), sticky="w")

        tk.Label(parent, text="字段名称：", font=("微软雅黑", 10), bg=bg).grid(row=0, column=2, sticky="w")
        self._add_label_var = tk.StringVar()
        tk.Entry(parent, textvariable=self._add_label_var, width=14, font=("微软雅黑", 10)).grid(row=0, column=3, padx=(0, 12), sticky="w")

        tk.Label(parent, text="控件类型：", font=("微软雅黑", 10), bg=bg).grid(row=0, column=4, sticky="w")
        self._add_type_var = tk.StringVar(value="combobox")
        type_combo = ttk.Combobox(
            parent, textvariable=self._add_type_var,
            values=FIELD_TYPES, state="readonly", width=10,
            font=("微软雅黑", 10)
        )
        type_combo.grid(row=0, column=5, padx=(0, 12), sticky="w")

        tk.Label(parent, text="填写值：", font=("微软雅黑", 10), bg=bg).grid(row=0, column=6, sticky="w")
        self._add_value_var = tk.StringVar()
        tk.Entry(parent, textvariable=self._add_value_var, width=16, font=("微软雅黑", 10)).grid(row=0, column=7, padx=(0, 12), sticky="w")

        tk.Button(
            parent, text="+ 添加字段",
            font=("微软雅黑", 10), bg="#34a853", fg="white",
            relief="flat", cursor="hand2", padx=8,
            command=self._add_field
        ).grid(row=0, column=8, padx=(0, 4))

    def _build_buttons(self, parent):
        """底部操作按钮"""
        tk.Button(
            parent, text="▶  开始填写",
            font=("微软雅黑", 11, "bold"), bg="#1a73e8", fg="white",
            relief="flat", cursor="hand2", padx=14, pady=6,
            command=self._run_autofill
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            parent, text="X  删除选中行",
            font=("微软雅黑", 10), bg="#ea4335", fg="white",
            relief="flat", cursor="hand2", padx=10, pady=6,
            command=self._delete_selected
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            parent, text="保存字段定义到 fields.py",
            font=("微软雅黑", 10), bg="#fbbc04", fg="#333",
            relief="flat", cursor="hand2", padx=10, pady=6,
            command=self._save_fields
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            parent, text="重置（重新加载 fields.py）",
            font=("微软雅黑", 10), bg="#e8eaed", fg="#333",
            relief="flat", cursor="hand2", padx=10, pady=6,
            command=self._reset_fields
        ).pack(side="left")

    def _build_log(self, parent):
        """日志文本框"""
        self.log_text = scrolledtext.ScrolledText(
            parent, height=8, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            state="disabled", wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

    # ── 表格操作 ──
    def _refresh_table(self):
        """清空并重绘 Treeview"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self._rows:
            self.tree.insert("", "end", values=(
                row["label"],
                row["field_id"],
                row["field_type"],
                row["value"],
            ))

    def _on_double_click(self, event):
        """双击"填写值"列 -> 弹出内联编辑"""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        col_index = int(col.replace("#", "")) - 1
        if col_index != 3:
            self._log("提示：双击【填写值】列可以编辑，其他列不可直接编辑（请删除后重新添加）")
            return

        item = self.tree.identify_row(event.y)
        if not item:
            return

        bbox = self.tree.bbox(item, col)
        if not bbox:
            return
        x, y, w, h = bbox

        current_val = self.tree.item(item, "values")[3]
        row_index = self.tree.index(item)

        entry_var = tk.StringVar(value=current_val)
        entry = tk.Entry(self.tree, textvariable=entry_var, font=("微软雅黑", 10))
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus()

        def commit(_event=None):
            new_val = entry_var.get()
            self._rows[row_index]["value"] = new_val
            entry.destroy()
            self._refresh_table()
            children = self.tree.get_children()
            if row_index < len(children):
                self.tree.selection_set(children[row_index])

        def cancel(_event=None):
            entry.destroy()

        entry.bind("<Return>", commit)
        entry.bind("<Tab>", commit)
        entry.bind("<Escape>", cancel)
        entry.bind("<FocusOut>", commit)

    def _add_field(self):
        """添加新字段行"""
        fid   = self._add_id_var.get().strip()
        label = self._add_label_var.get().strip()
        ftype = self._add_type_var.get().strip()
        value = self._add_value_var.get().strip()

        if not fid:
            messagebox.showwarning("提示", "字段 ID 不能为空")
            return
        if not label:
            messagebox.showwarning("提示", "字段名称不能为空")
            return
        if any(r["field_id"] == fid for r in self._rows):
            messagebox.showwarning("提示", f"字段 ID [{fid}] 已存在")
            return

        self._rows.append({"field_id": fid, "label": label, "field_type": ftype, "value": value})
        self._refresh_table()

        self._add_id_var.set("")
        self._add_label_var.set("")
        self._add_value_var.set("")
        self._log(f"已添加字段：[{label}]  id={fid}  type={ftype}")

    def _delete_selected(self):
        """删除选中的字段行"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中要删除的行")
            return
        index = self.tree.index(selected[0])
        label = self._rows[index]["label"]
        if messagebox.askyesno("确认删除", f"确认删除字段 [{label}]？"):
            self._rows.pop(index)
            self._refresh_table()
            self._log(f"已删除字段：[{label}]")

    def _clear_all_rows(self):
        """清空所有字段行"""
        if not self._rows:
            return
        if messagebox.askyesno("确认清空", f"确认清空全部 {len(self._rows)} 个字段？此操作不可撤销。"):
            self._rows.clear()
            self._refresh_table()
            self._log("已清空所有字段")

    def _save_fields(self):
        """将当前字段定义写回 fields.py"""
        save_fields_to_file(self._rows)
        messagebox.showinfo("保存成功", "字段定义已保存到 autofill/fields.py")
        self._log("字段定义已保存到 fields.py")

    def _reset_fields(self):
        """重新从 fields.py 加载字段（放弃当前未保存的修改）"""
        import importlib
        import autofill.fields as fm
        importlib.reload(fm)
        self._rows = [
            {
                "field_id":   f["field_id"],
                "label":      f["label"],
                "field_type": f["field_type"],
                "value":      "",
            }
            for f in fm.FIELD_DEFINITIONS
        ]
        self._refresh_table()
        self._log("已重新从 fields.py 加载字段定义（填写值已清空）")

    # ── 日志 ──
    def _log(self, msg: str):
        """向日志区追加一行（线程安全）"""
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _append)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ── 采集功能 ──
    def _run_scrape(self):
        """点击"采集并导入字段"：打开浏览器采集商品信息"""
        url = self._scrape_url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入商品详情页链接")
            return
        if "jxemall.com" not in url:
            messagebox.showwarning("提示", "请输入有效的江西省政府采购网商品详情页链接")
            return

        scrape_acc = self._get_selected_scrape()
        if not scrape_acc:
            messagebox.showwarning("提示", "请先选择一个采集账号")
            return

        self._clear_log()
        self._log("=" * 48)
        self._log("开始采集商品信息...")
        self._log(f"目标链接: {url}")
        self._log(f"采集账号: {scrape_acc['username']}")
        self._log("=" * 48)

        self._set_buttons_state("disabled")

        def run_in_thread():
            try:
                asyncio.run(self._async_scrape(url, scrape_acc))
            except Exception as e:
                self._log(f"[错误] {e}")
            finally:
                self.root.after(0, lambda: self._set_buttons_state("normal"))

        threading.Thread(target=run_in_thread, daemon=True).start()

    async def _async_scrape(self, detail_url: str, scrape_acc: dict):
        """在后台异步执行采集流程"""
        from playwright.async_api import async_playwright
        from autofill.config import HEADLESS, SLOW_MO, VIEWPORT
        from autofill.login import ensure_logged_in
        from autofill.scraper import scrape_goods

        import builtins
        original_print = builtins.print
        def gui_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            self._log(msg)
        builtins.print = gui_print

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=HEADLESS, slow_mo=SLOW_MO,
                    args=["--start-maximized"]
                )
                context = await browser.new_context(viewport=VIEWPORT, locale="zh-CN")
                page = await context.new_page()

                self._log("[采集步骤 1] 打开商品详情页...")
                await page.goto(detail_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(1000)

                self._log("[采集步骤 2] 检查登录状态...")
                await ensure_logged_in(page, scrape_acc["username"], scrape_acc["password"])

                if "goods/detail" not in page.url and "channelItemId" not in page.url:
                    self._log("[采集步骤 3] 重新导航到商品详情页...")
                    await page.goto(detail_url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(2000)

                await page.wait_for_load_state("domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)
                self._log(f"[采集步骤 3] 已到达商品详情页")

                self._log("[采集步骤 4] 开始提取字段信息...")
                scraped_fields = await scrape_goods(page, detail_url)

                if not scraped_fields:
                    self._log("[警告] 未提取到任何字段信息！")
                    self._log("  可能原因：页面未完全加载，或页面结构与预期不同")
                    self._log("浏览器保持打开，请手动检查页面内容。")
                    return

                self._log("=" * 48)
                self._log(f"采集完成！共提取 {len(scraped_fields)} 个字段，正在导入...")
                self._log("=" * 48)

                self.root.after(0, lambda: self._import_scraped_fields(scraped_fields))

                self._log("字段已导入到表格中，你可以检查并修改后点击【开始填写】发布。")
                self._log("提示：点【保存字段定义到 fields.py】可将采集到的字段结构永久保存。")

        finally:
            builtins.print = original_print

    def _import_scraped_fields(self, scraped_fields: list[dict]):
        """将采集结果导入到字段表（合并或替换）"""
        if self._rows:
            result = messagebox.askyesno(
                "导入方式",
                f"当前表格已有 {len(self._rows)} 个字段。\n\n"
                f"采集到 {len(scraped_fields)} 个字段。\n\n"
                f"点【是】：替换当前所有字段（用采集结果覆盖）\n"
                f"点【否】：合并（保留已有 + 新增采集到的字段）"
            )
            if result:
                self._rows = [
                    {
                        "field_id":   f["field_id"],
                        "label":      f["label"],
                        "field_type": f["field_type"],
                        "value":      f.get("value", ""),
                    }
                    for f in scraped_fields
                ]
                self._log("已替换为采集结果（全部字段已更新）")
            else:
                existing_ids = {r["field_id"] for r in self._rows}
                added = 0
                updated = 0
                for f in scraped_fields:
                    fid = f["field_id"]
                    if fid in existing_ids:
                        for r in self._rows:
                            if r["field_id"] == fid:
                                r["value"] = f.get("value", "")
                                updated += 1
                                break
                    else:
                        self._rows.append({
                            "field_id":   fid,
                            "label":      f["label"],
                            "field_type": f["field_type"],
                            "value":      f.get("value", ""),
                        })
                        existing_ids.add(fid)
                        added += 1
                self._log(f"合并完成：新增 {added} 个字段，更新 {updated} 个字段的值")
        else:
            self._rows = [
                {
                    "field_id":   f["field_id"],
                    "label":      f["label"],
                    "field_type": f["field_type"],
                    "value":      f.get("value", ""),
                }
                for f in scraped_fields
            ]
            self._log("已将采集结果导入到空表格")

        self._refresh_table()

    # ── 运行自动填写 ──
    def _run_autofill(self):
        """点击"开始填写"：收集数据 -> 在后台线程运行自动化"""
        fill_data = {r["field_id"]: r["value"] for r in self._rows if r["value"].strip()}
        if not fill_data:
            messagebox.showwarning("提示", "请至少为一个字段填写值")
            return

        target_url = self._fill_url_var.get().strip()
        if not target_url:
            messagebox.showwarning("提示", "请输入填写目标链接")
            return

        publish_acc = self._get_selected_publish()
        if not publish_acc:
            messagebox.showwarning("提示", "请先选择一个发布账号")
            return

        self._clear_log()
        self._log("=" * 48)
        self._log("开始自动填写流程...")
        self._log(f"发布账号: {publish_acc['username']}")
        self._log(f"目标链接: {target_url}")
        self._log(f"待填写 {len(fill_data)} 个字段：")
        for fid, val in fill_data.items():
            label = next((r["label"] for r in self._rows if r["field_id"] == fid), fid)
            self._log(f"  [{label}]: {val}")
        self._log("=" * 48)

        self._set_buttons_state("disabled")

        def run_in_thread():
            try:
                asyncio.run(self._async_run(fill_data, self._rows, target_url, publish_acc))
            except Exception as e:
                self._log(f"[错误] {e}")
            finally:
                self.root.after(0, lambda: self._set_buttons_state("normal"))

        threading.Thread(target=run_in_thread, daemon=True).start()

    async def _async_run(self, fill_data: dict, rows: list, target_url: str, publish_acc: dict):
        """在后台异步执行自动化（使用动态选择的账号）"""
        from playwright.async_api import async_playwright
        from autofill.config import HEADLESS, SLOW_MO, VIEWPORT
        from autofill.login import ensure_logged_in
        from autofill.filler import fill_field

        field_defs = [
            {"field_id": r["field_id"], "label": r["label"], "field_type": r["field_type"]}
            for r in rows
            if r["field_id"] in fill_data
        ]

        import builtins
        original_print = builtins.print
        def gui_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            self._log(msg)
        builtins.print = gui_print

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=HEADLESS, slow_mo=SLOW_MO,
                    args=["--start-maximized"]
                )
                context = await browser.new_context(viewport=VIEWPORT, locale="zh-CN")
                page = await context.new_page()

                self._log("[步骤 1] 打开目标页面...")
                await page.goto(target_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(1000)

                self._log("[步骤 2] 检查登录状态...")
                await ensure_logged_in(page, publish_acc["username"], publish_acc["password"])

                if "goods/publish" not in page.url and "goods-center" not in page.url:
                    self._log("[步骤 3] 重新导航到发布页...")
                    await page.goto(target_url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(2000)

                await page.wait_for_load_state("domcontentloaded", timeout=20000)
                await page.wait_for_timeout(5000)
                self._log(f"[步骤 3] 已到达发布页")

                self._log("[步骤 4] 滚动页面触发懒加载渲染...")
                total_height = await page.evaluate("() => document.body.scrollHeight")
                for y in range(0, total_height, 300):
                    await page.evaluate(f"window.scrollTo(0, {y})")
                    await page.wait_for_timeout(100)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1500)
                self._log("  页面滚动完成")

                self._log("[步骤 5] 开始填写字段...")
                errors = []
                for fd in field_defs:
                    value = fill_data[fd["field_id"]]
                    try:
                        await fill_field(page, fd, value)
                        await page.wait_for_timeout(300)
                    except Exception as e:
                        errors.append((fd["label"], str(e)))

                self._log("=" * 48)
                if not errors:
                    self._log("所有字段填写完成！")
                else:
                    self._log(f"填写完成，但有 {len(errors)} 个字段失败：")
                    for label, msg in errors:
                        self._log(f"  [{label}] 错误: {msg}")
                self._log("=" * 48)
                self._log("浏览器将保持打开，请手动检查页面结果。")

        finally:
            builtins.print = original_print

    def _set_buttons_state(self, state: str):
        """启用/禁用所有按钮"""
        for widget in self.root.winfo_children():
            self._set_frame_buttons(widget, state)

    def _set_frame_buttons(self, widget, state):
        if isinstance(widget, (tk.Button,)):
            try:
                widget.config(state=state)
            except Exception:
                pass
        for child in widget.winfo_children():
            self._set_frame_buttons(child, state)


# ─────────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────────
def main():
    if sys.platform == "win32":
        import io
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = tk.Tk()
    app = AutofillGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
