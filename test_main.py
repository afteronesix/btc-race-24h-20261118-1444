import unittest
from main import Strategy


def orders(prices):
    bot = Strategy()
    return [bot.step(p, 10**9, 0, 10**12, False) for p in prices]


class StrategyTest(unittest.TestCase):
    def test_flat_and_down_never_buy(self):
        self.assertFalse(any(orders([100_000] * 100)))
        self.assertFalse(any(orders(range(100_000, 99_000, -10))))

    def test_rising_market_emits_cash_bounded_buy(self):
        action = next(x for x in orders(range(100_000, 102_000, 20)) if x)
        self.assertEqual(action['side'], 'buy')
        self.assertGreaterEqual(action['notional_quote_units'], 1_000_000)
        self.assertLessEqual(action['notional_quote_units'], 10**9)

    def test_warmup_and_protective_exit(self):
        bot = Strategy()
        self.assertFalse(any(bot.step(p, 10**9, 0, 10**12, True) for p in range(100_000, 102_000, 20)))
        bot.step(102_000, 0, 500, 10**12, False)
        action = bot.step(100_000, 0, 500, 10**12, False)
        self.assertEqual((action['side'], action['qty']), ('sell', 500))

    def test_deterministic(self):
        stream = list(range(100_000, 102_000, 20))
        self.assertEqual(orders(stream), orders(stream))
