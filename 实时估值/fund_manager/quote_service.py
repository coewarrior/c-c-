from PySide6.QtCore import QThread, Signal, QMutex
from providers import RealProvider
import time
from datetime import datetime, time as dtime
from chinese_calendar import is_workday


TRADING_REFRESH_SEC = 10
NON_TRADING_REFRESH_SEC = 120


class QuoteWorker(QThread):
    price_updated = Signal(int, dict)

    def __init__(self, funds_data):
        super().__init__()
        self.funds_data = funds_data
        self.running = True
        self.provider = RealProvider()
        self._force_trigger = False
        self.mutex = QMutex()

    def set_funds(self, funds):
        self.mutex.lock()
        self.funds_data = funds
        self.mutex.unlock()

    def trigger_now(self):
        self._force_trigger = True

    def run(self):
        while self.running:
            self.mutex.lock()
            current_list = list(self.funds_data)
            self.mutex.unlock()

            if current_list:
                for fund in current_list:
                    if not self.running:
                        break
                    try:
                        res = self.provider.fetch(fund['code'])
                        self.price_updated.emit(fund['id'], res)
                    except Exception as e:
                        print(f"Fetch error for {fund['code']}: {e}")
                    time.sleep(0.2)

            self._force_trigger = False

            wait_limit = self._next_wait_seconds()
            for _ in range(wait_limit):
                if not self.running or self._force_trigger:
                    break
                time.sleep(1)

    def _next_wait_seconds(self):
        now = datetime.now()
        if not is_workday(now.date()):
            return NON_TRADING_REFRESH_SEC
        # trading hours 09:30-15:00
        t = now.time()
        if dtime(9, 30) <= t <= dtime(15, 0):
            return TRADING_REFRESH_SEC
        return NON_TRADING_REFRESH_SEC

    def stop(self):
        self.running = False
        self.wait()