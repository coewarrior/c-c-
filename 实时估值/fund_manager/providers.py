from datetime import datetime, timedelta
import requests
import re
import json


class BaseProvider:
    def fetch(self, code):
        raise NotImplementedError

    def get_fund_name(self, code):
        raise NotImplementedError


class RealProvider(BaseProvider):
    def __init__(self):
        self._actual_cache = {}  # code -> (ts, rate, date_str)

    def fetch(self, code):
        try:
            url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            headers = {'Referer': 'http://fund.eastmoney.com/'}
            resp = requests.get(url, headers=headers, timeout=5)
            content = resp.text

            result = {'ok': False, 'is_official': False, 'source': '\u5929\u5929\u57fa\u91d1'}

            if "jsonpgz" in content:
                data_str = re.findall(r'jsonpgz\((.*)\);', content)[0]
                data = json.loads(data_str)
                gz_time_full = data['gztime']

                result.update({
                    'est_nav': float(data['gsz']),
                    'est_rate': float(data['gszzl']) / 100.0,
                    'time_str': data['gztime'].split(' ')[1],
                    'nav': float(data.get('dwjz')) if data.get('dwjz') else None,
                    'nav_date': data.get('jzrq'),
                    'ok': True,
                    'is_official': False
                })

                if "15:00" in gz_time_full and datetime.now().hour >= 20:
                    result['is_official'] = True

                actual_rate, actual_date = self.get_actual_rate(code)
                if actual_rate is not None:
                    result['actual_rate'] = actual_rate
                    result['actual_date'] = actual_date

                return result
            return {'ok': False, 'error': '\u65e0\u6548\u4ee3\u7801', 'source': 'Real'}
        except Exception as e:
            return {'ok': False, 'error': str(e), 'source': 'Real'}

    def get_fund_name(self, code):
        try:
            url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            resp = requests.get(url, timeout=5)
            if "jsonpgz" in resp.text:
                data_str = re.findall(r'jsonpgz\((.*)\);', resp.text)[0]
                data = json.loads(data_str)
                return data['name']
        except Exception:
            pass
        return None

    def get_actual_rate(self, code):
        cached = self._actual_cache.get(code)
        if cached:
            ts, rate, date_str = cached
            if datetime.now() - ts < timedelta(minutes=10):
                return rate, date_str

        try:
            url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
            resp = requests.get(url, timeout=6)
            text = resp.text
            m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", text, re.S)
            if not m:
                return None, None
            data = json.loads(m.group(1))
            if len(data) < 2:
                return None, None
            last = data[-1]
            prev = data[-2]
            last_nav = float(last.get('y') or 0)
            prev_nav = float(prev.get('y') or 0)
            if prev_nav <= 0:
                return None, None
            actual_rate = (last_nav - prev_nav) / prev_nav
            date_str = datetime.fromtimestamp(last.get('x') / 1000).strftime("%Y-%m-%d")
            self._actual_cache[code] = (datetime.now(), actual_rate, date_str)
            return actual_rate, date_str
        except Exception:
            return None, None


class MockProvider(BaseProvider):
    def fetch(self, code):
        now = datetime.now()
        return {
            'est_nav': 1.2345,
            'est_rate': 0.012,
            'actual_rate': 0.008,
            'actual_date': now.strftime("%Y-%m-%d"),
            'time_str': now.strftime("%H:%M:%S"),
            'is_official': now.hour >= 20,
            'ok': True
        }

    def get_fund_name(self, code):
        return f"\u6a21\u62df\u57fa\u91d1({code})"