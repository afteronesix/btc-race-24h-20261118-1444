"""Causal trend filter for the make.fun paper-trading replay."""
import json
import sys
from collections import deque


class Strategy:
    def __init__(self):
        self.history = deque(maxlen=121)
        self.fast = self.slow = None
        self.peak = 0
        self.cooldown = 0

    def step(self, price, cash, qty, depth, warmup=False):
        self.history.append(price)
        self.fast = price if self.fast is None else self.fast + (price-self.fast)*2/17
        self.slow = price if self.slow is None else self.slow + (price-self.slow)*2/81
        if warmup:
            return None
        if qty:
            self.peak = max(self.peak, price)
            if price < self.peak * .994 or (self.fast < self.slow and price < self.slow):
                self.cooldown = 20
                return dict(side='sell', symbol='CBBTC', qty=qty, max_slippage_bps=150)
            return None
        self.peak = price
        if self.cooldown:
            self.cooldown -= 1
            return None
        if len(self.history) < 61:
            return None
        momentum = price / self.history[-61] - 1
        if momentum > .003 and self.fast > self.slow * 1.0005 and price > self.fast:
            amount = min(cash * 3 // 4, depth // 2000)
            if amount >= 1_000_000:
                return dict(side='buy', symbol='CBBTC', notional_quote_units=amount, max_slippage_bps=100)
        return None


def run():
    bot = Strategy()
    warmup = 0
    for line in sys.stdin:
        msg = json.loads(line)
        if msg['type'] == 'hello':
            warmup = msg.get('warmup_bars', 0)
        elif msg['type'] == 'batch':
            actions = []
            for bar in msg['bars']:
                if bar['symbol'] != 'CBBTC':
                    continue
                account = msg['account']
                qty = sum(int(p['qty']) for p in account['positions'] if p['symbol']=='CBBTC')
                depth = min(map(int,bar['c_depth']))
                action = bot.step(int(bar['c']), int(account['cash_quote_units']), qty, depth, msg['seq'] < warmup)
                if action:
                    field = 'qty' if action['side']=='sell' else 'notional_quote_units'
                    action[field] = str(action[field])
                    action['client_id'] = 't'+str(msg['seq'])
                    actions.append(action)
            print(json.dumps(dict(type='reply',seq=msg['seq'],orders=actions),separators=(',',':')),flush=True)
        elif msg['type'] == 'done':
            break
        else:
            raise ValueError('Unknown protocol message')


if __name__ == '__main__':
    run()
