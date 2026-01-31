import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QTableWidget, QTableWidgetItem,
                               QPushButton, QLabel, QHeaderView, QMessageBox, QAbstractItemView, QInputDialog,
                               QDialog, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from datetime import datetime
import exchange_calendars as xcals

import database
import calc
from quote_service import QuoteWorker
from ui_components import AddFundDialog, AddTradeDialog

COLOR_RED = QColor(220, 50, 50)
COLOR_GREEN = QColor(50, 150, 50)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("基金持仓管家")
        self.resize(1100, 650)
        database.init_db()
        self.cache = {}
        self.trade_dialog = None
        self.current_account = "全部"
        self.setup_ui()
        self.load_data()

        # 启动估值刷新线程
        self.worker = QuoteWorker([])
        self.worker.price_updated.connect(self.on_price_updated)
        self.update_worker_funds()
        self.worker.start()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 顶部总览
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)
        self.lbl_mv = QLabel("总市值: 0.00")
        self.lbl_today = QLabel("今日盈亏: 0.00")
        self.lbl_total = QLabel("累计盈亏: 0.00")
        for l in [self.lbl_mv, self.lbl_today, self.lbl_total]:
            l.setProperty("card", True)
            summary_layout.addWidget(l)
        layout.addLayout(summary_layout)

        # 仓位 Tab（按钮）
        self.tabs_widget = QWidget()
        self.tabs_layout = QHBoxLayout(self.tabs_widget)
        self.tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_layout.setSpacing(8)
        layout.addWidget(self.tabs_widget)
        self.refresh_accounts()

        # 操作按钮
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)
        self.btn_add = QPushButton("添加新基金")
        self.btn_trade = QPushButton("录入交易")
        self.btn_account = QPushButton("管理仓位")
        self.btn_delete = QPushButton("删除基金")
        self.btn_refresh = QPushButton("手动刷新")

        self.btn_add.setProperty("primary", True)
        self.btn_refresh.setProperty("accent", True)
        self.btn_delete.setProperty("danger", True)

        btn_bar.addWidget(self.btn_add)
        btn_bar.addWidget(self.btn_trade)
        btn_bar.addWidget(self.btn_account)
        btn_bar.addWidget(self.btn_delete)
        btn_bar.addWidget(self.btn_refresh)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        self.btn_add.clicked.connect(self.show_add_fund)
        self.btn_trade.clicked.connect(self.show_add_trade)
        self.btn_account.clicked.connect(self.add_account)
        self.btn_delete.clicked.connect(self.delete_selected_fund)
        self.btn_refresh.clicked.connect(self.manual_refresh)

        # 表格
        self.table = QTableWidget()
        headers = ["ID", "代码", "名称", "持仓市值", "今日涨跌", "实际涨跌", "今日盈亏", "累计盈亏", "收益率", "更新时间"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnHidden(0, True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(90)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.setStyleSheet(self._style_sheet())

    def _style_sheet(self):
        return (
            "QMainWindow {"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffe0c2, stop:0.5 #ffc18f, stop:1 #ffd7b0);"
            " }"
            "QLabel[card=\"true\"] {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fff6ee, stop:1 #ffd8c0);"
            " border: 1px solid #f3b991; border-radius: 14px;"
            " padding: 14px 16px; font-size: 18px; font-weight: 700; color: #3b2f2f;"
            " }"
            "QPushButton {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f3e1d1);"
            " color: #3b2f2f; border: 1px solid #d6a57f; border-radius: 10px; padding: 6px 16px;"
            " font-weight: 600;"
            " }"
            "QPushButton[primary=\"true\"] {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6aa9ff, stop:1 #2b6adf);"
            " color: #ffffff; border: 1px solid #2b6adf; }"
            "QPushButton[accent=\"true\"] {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #47d6a6, stop:1 #11a978);"
            " color: #ffffff; border: 1px solid #11a978; }"
            "QPushButton[danger=\"true\"] {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff7a5f, stop:1 #e43d2c);"
            " color: #ffffff; border: 1px solid #e43d2c; }"
            "QPushButton[tab=\"true\"] {"
            " border-radius: 18px; padding: 4px 16px; background: #ffe8d1; border: 1px solid #e8b68f; }"
            "QPushButton[tab=\"true\"][selected=\"true\"] {"
            " background: #ffcf9f; border: 1px solid #d98957; color: #2f1f15; }"
            "QTableWidget {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fff3e6, stop:1 #ffd2ad);"
            " border: 1px solid #e0a879; border-radius: 12px; gridline-color: #e6b890;"
            " selection-background-color: #ffd0a8; selection-color: #3b2f2f;"
            " }"
            "QHeaderView::section {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffe8d1, stop:1 #f3b688);"
            " color: #3b2f2f; border: none; padding: 8px; font-weight: 700;"
            " }"
            "QTableWidget::item { padding: 6px; color: #3b2f2f; }"
            "QTableWidget::item:selected { background: #ffc99a; color: #3b2f2f; }"
        )

    def refresh_accounts(self):
        accounts = ["全部"] + database.get_accounts()
        while self.tabs_layout.count():
            item = self.tabs_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for name in accounts:
            btn = QPushButton(name)
            btn.setProperty("tab", True)
            btn.setProperty("selected", name == self.current_account)
            btn.clicked.connect(lambda _, n=name: self.set_account(n))
            self.tabs_layout.addWidget(btn)
        self.tabs_layout.addStretch()

    def set_account(self, name):
        self.current_account = name
        self.refresh_accounts()
        self.load_data()

    def load_data(self):
        funds = database.get_all_funds_with_positions()
        if self.current_account and self.current_account != "全部":
            funds = [f for f in funds if (f.get("account") or "默认账户") == self.current_account]
        self.table.setRowCount(0)
        self.cache = {}
        for f in funds:
            self.cache[f["id"]] = {"info": f, "quote": None, "metrics": None}
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(f["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(f["code"]))
            self.table.setItem(row, 2, QTableWidgetItem(f["name"]))
            self.update_row_display(row, f, None, None)
        self.update_worker_funds()

    def update_worker_funds(self):
        if hasattr(self, "worker"):
            funds_list = [v["info"] for v in self.cache.values()]
            self.worker.set_funds(funds_list)

    def update_row_display(self, row, info, quote, metrics):
        def set_item(col, txt, color=None):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(Qt.AlignCenter)
            if color:
                it.setForeground(color)
            self.table.setItem(row, col, it)

        if metrics and quote:
            set_item(3, f"{metrics['market_value']:,.2f}")
            c_day = COLOR_RED if metrics["today_pnl"] > 0 else COLOR_GREEN if metrics["today_pnl"] < 0 else Qt.black
            rate_prefix = "估" if not quote.get("is_official") else "净"
            set_item(4, f"{rate_prefix}{quote['est_rate'] * 100:+.2f}%", c_day)
            actual_rate = quote.get("actual_rate_display", quote.get("actual_rate"))
            actual_date = quote.get("actual_date_display", quote.get("actual_date"))
            if actual_rate is None:
                set_item(5, "--")
            else:
                actual_text = f"{actual_rate * 100:+.2f}%"
                if actual_date:
                    actual_text += f" ({actual_date})"
                set_item(5, actual_text, COLOR_RED if actual_rate > 0 else COLOR_GREEN if actual_rate < 0 else Qt.black)
            set_item(6, f"{metrics['today_pnl']:+,.2f}", c_day)
            c_total = COLOR_RED if metrics["total_pnl"] > 0 else COLOR_GREEN if metrics["total_pnl"] < 0 else Qt.black
            set_item(7, f"{metrics['total_pnl']:+,.2f}", c_total)
            set_item(8, f"{metrics['total_rate'] * 100:+.2f}%", c_total)
            date_str = quote.get("nav_date") or datetime.now().strftime("%Y-%m-%d")
            time_str = f"{quote['time_str']} {date_str}" + (" (已校准)" if quote.get("is_official") else "")
            set_item(9, time_str)
        else:
            for i in range(3, 10):
                set_item(i, "--")

    @Slot(int, dict)
    def on_price_updated(self, fid, quote):
        if fid not in self.cache:
            return
        actual_rate_display, actual_date_display, use_actual_for_pnl = self._resolve_actual_rate(quote)
        quote_display = dict(quote)
        quote_display["actual_rate_display"] = actual_rate_display
        quote_display["actual_date_display"] = actual_date_display
        self.cache[fid]["quote"] = quote_display
        if quote.get("ok"):
            info = self.cache[fid]["info"]
            try:
                if calc.reconcile_pending_trades(
                    fid,
                    quote.get("est_nav"),
                    nav=quote.get("nav"),
                    nav_date=quote.get("nav_date"),
                    now_dt=datetime.now(),
                ):
                    updated = database.get_fund_with_position(fid)
                    if updated:
                        self.cache[fid]["info"] = updated
                        info = updated
            except Exception:
                pass
            rate_for_pnl = actual_rate_display if use_actual_for_pnl and actual_rate_display is not None else quote["est_rate"]
            m = calc.calc_display_metrics(info["shares"], info["cost_amount"], quote["est_nav"], rate_for_pnl)
            self.cache[fid]["metrics"] = m
            row = self.find_row(fid)
            if row is not None:
                self.update_row_display(row, info, quote_display, m)
            if self.trade_dialog and self.trade_dialog.isVisible():
                current_row = self.table.currentRow()
                if current_row >= 0:
                    current_fid = int(self.table.item(current_row, 0).text())
                    if current_fid == fid:
                        self.trade_dialog.set_latest_price(quote.get("est_nav"))
        self.update_summary()

    def _resolve_actual_rate(self, quote):
        actual_rate = quote.get("actual_rate")
        actual_date = quote.get("actual_date")
        if actual_rate is None or not actual_date:
            return None, None, False
        today_str = datetime.now().strftime("%Y-%m-%d")
        if actual_date == today_str:
            return actual_rate, actual_date, True
        try:
            if not xcals.get_calendar("XSHG").is_session(datetime.now().date()):
                return actual_rate, actual_date, True
        except Exception:
            if datetime.now().weekday() >= 5:
                return actual_rate, actual_date, True
        return None, None, False

    def update_summary(self):
        mv, day, tot = 0, 0, 0
        for v in self.cache.values():
            if v["metrics"]:
                mv += v["metrics"]["market_value"]
                day += v["metrics"]["today_pnl"]
                tot += v["metrics"]["total_pnl"]

        self.lbl_mv.setText(f"总市值: {mv:,.2f}")
        self.lbl_today.setText(f"今日盈亏: {day:+,.2f}")
        self.lbl_today.setStyleSheet(
            f"color: {'red' if day > 0 else 'green' if day < 0 else 'black'}; font-size: 18px; font-weight: 600; border: 1px solid #e5e7eb; padding: 12px 14px; background: white; border-radius: 8px;")
        self.lbl_total.setText(f"累计盈亏: {tot:+,.2f}")
        self.lbl_total.setStyleSheet(
            f"color: {'red' if tot > 0 else 'green' if tot < 0 else 'black'}; font-size: 18px; font-weight: 600; border: 1px solid #e5e7eb; padding: 12px 14px; background: white; border-radius: 8px;")

    def find_row(self, fid):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if not item:
                continue
            try:
                if int(item.text()) == fid:
                    return r
            except Exception:
                continue
        return None

    def manual_refresh(self):
        if hasattr(self, "worker"):
            self.btn_refresh.setEnabled(False)
            self.btn_refresh.setText("刷新中...")
            self.worker.trigger_now()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: (self.btn_refresh.setEnabled(True), self.btn_refresh.setText("手动刷新")))

    def show_add_fund(self):
        dlg = AddFundDialog(self)
        if dlg.exec():
            code, name, account = dlg.get_data()
            if code and name:
                success, msg = database.add_fund(code, name, account)
                if success:
                    self.load_data()
                else:
                    QMessageBox.critical(self, "错误", msg)

    def add_account(self):
        dlg = ManageAccountsDialog(self)
        dlg.exec()
        self.refresh_accounts()
        self.load_data()

    def show_add_trade(self):
        row = self.table.currentRow()
        if row < 0:
            return
        fid = int(self.table.item(row, 0).text())
        latest_nav = None
        quote = self.cache.get(fid, {}).get("quote")
        if quote and quote.get("ok"):
            latest_nav = quote.get("est_nav")
        self.trade_dialog = AddTradeDialog(self.cache[fid]["info"], self, latest_nav)
        if self.trade_dialog.exec():
            d = self.trade_dialog.get_data()
            database.add_trade(fid, d["type"], d["date"], d["amount"], d["shares"], d["price"], d["fee"], d["note"])
            calc.recalculate_position(fid)
            self.load_data()
        self.trade_dialog = None

    def delete_selected_fund(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一只基金")
            return
        fid = int(self.table.item(row, 0).text())
        code = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        name = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除基金 {name} ({code})?\n相关交易和持仓都会被删除。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        success, msg = database.delete_fund(fid)
        if success:
            self.load_data()
        else:
            QMessageBox.critical(self, "错误", msg)

    def closeEvent(self, event):
        if hasattr(self, "worker"):
            self.worker.stop()
        event.accept()


class ManageAccountsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理仓位")
        self.setFixedSize(360, 360)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setDragDropOverwriteMode(False)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("新增仓位")
        self.btn_rename = QPushButton("重命名")
        self.btn_up = QPushButton("上移")
        self.btn_down = QPushButton("下移")
        self.btn_del = QPushButton("删除仓位")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_rename)
        btn_row.addWidget(self.btn_up)
        btn_row.addWidget(self.btn_down)
        btn_row.addWidget(self.btn_del)
        layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self.add_account)
        self.btn_rename.clicked.connect(self.rename_account)
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down.clicked.connect(self.move_down)
        self.btn_del.clicked.connect(self.delete_account)
        self.list_widget.model().rowsMoved.connect(self.persist_order)
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for name in database.get_accounts():
            self.list_widget.addItem(QListWidgetItem(name))

    def add_account(self):
        name, ok = QInputDialog.getText(self, "新增仓位", "仓位名称:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        success, msg = database.add_account(name)
        if not success:
            QMessageBox.warning(self, "提示", msg)
        self.refresh_list()

    def delete_account(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除仓位「{name}」？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        success, msg = database.delete_account(name)
        if not success:
            QMessageBox.warning(self, "提示", msg)
        self.refresh_list()

    def rename_account(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, "重命名仓位", "新名称:", text=old_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        success, msg = database.rename_account(old_name, new_name)
        if not success:
            QMessageBox.warning(self, "提示", msg)
        self.refresh_list()

    def move_up(self):
        row = self.list_widget.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)

    def move_down(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= self.list_widget.count() - 1:
            return
        self._swap_rows(row, row + 1)

    def _swap_rows(self, row_a, row_b):
        item_a = self.list_widget.item(row_a)
        item_b = self.list_widget.item(row_b)
        if not item_a or not item_b:
            return
        name_a = item_a.text()
        name_b = item_b.text()
        item_a.setText(name_b)
        item_b.setText(name_a)
        self.list_widget.setCurrentRow(row_b)
        self.persist_order()

    def persist_order(self, *args):
        names = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        database.set_accounts_order(names)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
