from database import get_trades_by_fund, update_position, update_trade_shares
from datetime import datetime, timedelta
import exchange_calendars as xcals

def recalculate_position(fund_id):
    trades = get_trades_by_fund(fund_id)
    current_shares = 0.0
    current_cost = 0.0
    for trade in trades:
        t_type = trade['type']
        shares = float(trade['shares'])
        amount = float(trade['amount'])
        fee = float(trade['fee'])
        if t_type == 'buy':
            if shares > 0:
                current_shares += shares
                current_cost += (amount + fee)
        elif t_type == 'sell':
            if current_shares > 0:
                avg_cost_per_share = current_cost / current_shares
            else:
                avg_cost_per_share = 0
            if shares > current_shares:
                 shares = current_shares
            reduced_cost = avg_cost_per_share * shares
            current_shares -= shares
            current_cost -= reduced_cost
            current_cost -= fee
    if current_shares < 0.0001:
        current_shares = 0
        current_cost = 0
    update_position(fund_id, current_shares, current_cost)
    return current_shares, current_cost

_XSHG = xcals.get_calendar("XSHG")

def _add_trading_days(d, n):
    if n == 0:
        return d
    step = 1 if n > 0 else -1
    remaining = abs(n)
    cur = d
    while remaining > 0:
        cur = cur + timedelta(days=step)
        if _XSHG.is_session(cur):
            remaining -= 1
    return cur


def reconcile_pending_trades(fund_id, est_nav, nav=None, nav_date=None, now_dt=None):
    if now_dt is None:
        now_dt = datetime.now()
    changed = False
    trades = get_trades_by_fund(fund_id)
    for trade in trades:
        if trade['type'] == 'buy' and float(trade['shares']) <= 0 and float(trade['amount']) > 0:
            try:
                trade_time = datetime.strptime(trade['trade_time'], "%Y-%m-%d %H:%M:%S")
            except Exception:
                trade_time = now_dt
            trade_date = trade_time.date()
            # T+1: before 15:00 confirm next trading day;
            # after 15:00 confirm the trading day after next.
            base_date = trade_date
            if trade_time.time() >= datetime.strptime("15:00:00", "%H:%M:%S").time():
                base_date = _add_trading_days(trade_date, 1)
            target_date = _add_trading_days(base_date, 1)

            if now_dt.date() < target_date:
                continue

            price = None
            if nav and nav_date:
                try:
                    nav_dt = datetime.strptime(nav_date, "%Y-%m-%d").date()
                    if nav_dt >= target_date:
                        price = float(nav)
                except Exception:
                    pass
            if price is None:
                if est_nav is None or est_nav <= 0:
                    continue
                price = float(est_nav)

            shares = float(trade['amount']) / price
            update_trade_shares(trade['id'], shares, price)
            changed = True
    if changed:
        recalculate_position(fund_id)
    return changed

def calc_display_metrics(shares, cost_amount, est_nav, est_rate):
    if shares <= 0:
        return {"market_value": 0.0, "today_pnl": 0.0, "total_pnl": 0.0, "total_rate": 0.0}
    mv = shares * est_nav
    today_pnl = mv * est_rate
    total_pnl = mv - cost_amount
    total_rate = total_pnl / cost_amount if cost_amount != 0 else 0.0
    return {"market_value": mv, "today_pnl": today_pnl, "total_pnl": total_pnl, "total_rate": total_rate}
