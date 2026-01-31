from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QComboBox, QDateTimeEdit,
                               QFormLayout, QDoubleSpinBox, QMessageBox)
from PySide6.QtCore import QDateTime, Qt
from providers import RealProvider, MockProvider
import database


class AddFundDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加基金")
        self.setFixedSize(360, 200)

        # 内部使用 RealProvider 尝试获取名称
        self.provider = RealProvider()

        layout = QFormLayout()
        self.form_layout = layout

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("输入6位代码，如 161725")

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("自动获取中...")
        self.name_edit.setReadOnly(True)
        self.name_edit.setStyleSheet("background-color: #f3f4f6;")

        self.account_combo = QComboBox()
        accounts = database.get_accounts()
        if not accounts:
            accounts = ["默认账户"]
        self.account_combo.addItems(accounts)

        layout.addRow("基金代码:", self.code_edit)
        layout.addRow("基金名称:", self.name_edit)
        layout.addRow("仓位:", self.account_combo)

        self.status_label = QLabel("输入代码后点击确认，将自动查询名称")
        self.status_label.setStyleSheet("color: #6b7280; font-size: 11px;")

        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确认添加")
        self.btn_cancel = QPushButton("取消")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)

        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(self.status_label)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        self.btn_ok.clicked.connect(self.handle_confirm)
        self.btn_cancel.clicked.connect(self.reject)

    def handle_confirm(self):
        code = self.code_edit.text().strip()
        if len(code) != 6:
            QMessageBox.warning(self, "错误", "请输入正确的6位基金代码")
            return

        self.status_label.setText("正在联网查询基金名称...")
        self.btn_ok.setEnabled(False)

        name = self.provider.get_fund_name(code)
        if not name:
            name = MockProvider().get_fund_name(code)

        if name:
            self.name_edit.setText(name)
            self.status_label.setText("查询成功")
            self.accept()
        else:
            self.status_label.setText("未找到该基金，请检查代码")
            self.btn_ok.setEnabled(True)

    def get_data(self):
        return self.code_edit.text().strip(), self.name_edit.text().strip(), self.account_combo.currentText().strip()


class AddTradeDialog(QDialog):
    def __init__(self, current_fund_info, parent=None, latest_est_nav=None):
        super().__init__(parent)
        self.setWindowTitle(f"录入交易 - {current_fund_info['name']}")
        self.setFixedSize(400, 380)
        self.latest_est_nav = latest_est_nav

        layout = QFormLayout()
        self.form_layout = layout
        self.type_combo = QComboBox()
        self.type_combo.addItems(["买入 (Buy)", "卖出 (Sell)"])
        self.time_edit = QDateTimeEdit()
        self.time_edit.setCalendarPopup(True)
        self.time_edit.setDateTime(QDateTime.currentDateTime())
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 100000000)
        self.amount_spin.setDecimals(2)
        self.shares_spin = QDoubleSpinBox()
        self.shares_spin.setRange(0, 100000000)
        self.shares_spin.setDecimals(4)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 100000000)
        self.price_spin.setDecimals(4)
        self.price_spin.setSingleStep(0.0001)
        self.price_spin.setReadOnly(True)
        if self.latest_est_nav:
            self.price_spin.setValue(float(self.latest_est_nav))
        self.fee_spin = QDoubleSpinBox()
        self.fee_spin.setValue(0)
        self.note_edit = QLineEdit()
        self.buy_shares_label = QLabel("--")

        layout.addRow("类型:", self.type_combo)
        layout.addRow("交易时间:", self.time_edit)
        layout.addRow("金额(买入):", self.amount_spin)
        layout.addRow("成交净值:", self.price_spin)
        layout.addRow("自动份额:", self.buy_shares_label)
        layout.addRow("卖出份额:", self.shares_spin)
        layout.addRow("费用:", self.fee_spin)
        layout.addRow("备注:", self.note_edit)

        self.btn_ok = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(self.btn_ok)
        main_layout.addWidget(self.btn_cancel)
        self.setLayout(main_layout)

        self.btn_ok.clicked.connect(self.handle_accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.type_combo.currentIndexChanged.connect(self.update_mode)
        self.amount_spin.valueChanged.connect(self.update_buy_shares)
        self.price_spin.valueChanged.connect(self.update_buy_shares)
        self.update_mode()

    def update_mode(self):
        is_buy = self.type_combo.currentIndex() == 0
        self.amount_spin.setVisible(is_buy)
        self.price_spin.setVisible(is_buy)
        self.buy_shares_label.setVisible(is_buy)
        self.shares_spin.setVisible(not is_buy)
        for w in (self.amount_spin, self.price_spin, self.buy_shares_label, self.shares_spin):
            label = self.form_layout.labelForField(w)
            if label:
                label.setVisible(w.isVisible())
        self.update_buy_shares()

    def update_buy_shares(self):
        if self.type_combo.currentIndex() != 0:
            return
        amount = self.amount_spin.value()
        price = self.price_spin.value()
        if price > 0:
            shares = amount / price
            self.buy_shares_label.setText(f"{shares:,.4f}")
        else:
            self.buy_shares_label.setText("--")

    def set_latest_price(self, price):
        if price is None:
            return
        self.price_spin.setValue(float(price))
        self.update_buy_shares()

    def handle_accept(self):
        is_buy = self.type_combo.currentIndex() == 0
        if is_buy:
            if self.amount_spin.value() <= 0:
                QMessageBox.warning(self, "错误", "请输入正确的买入金额")
                return
            if self.price_spin.value() <= 0:
                QMessageBox.warning(self, "错误", "请先刷新净值")
                return
        else:
            if self.shares_spin.value() <= 0:
                QMessageBox.warning(self, "错误", "请输入正确的卖出份额")
                return
        self.accept()

    def get_data(self):
        is_buy = self.type_combo.currentIndex() == 0
        amount = self.amount_spin.value() if is_buy else 0
        # Mode 2: buy shares are confirmed later (T+1), so store 0 now.
        price = 0 if is_buy else 0
        shares = 0 if is_buy else self.shares_spin.value()
        return {
            "type": "buy" if is_buy else "sell",
            "date": self.time_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "amount": amount,
            "shares": shares,
            "fee": self.fee_spin.value(),
            "price": price,
            "note": self.note_edit.text()
        }
