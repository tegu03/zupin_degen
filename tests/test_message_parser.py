import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.message_parser import is_result_message, parse_call_message, parse_result_message

CALL_TEXT = """
$PAIREX — SMART MONEY
Launch a coin priced in Canadian dollars, euros, yen or any of 158 supported world currencies.

MC $87.9k · Liq $24.1k · 19m old
5m ▲49% · 1h ▲116% · 6h ▲116% · 24h ▲116%
Vol 1h $190.1k · 24h $190.1k · 1,609 buys / 1,193 sells
Holders 532 · reported top-10 38% · legit 43 degen

Reported wallet stats: win 44.3% · 787 tokens · realized +$45,654.44
Current audit: honeypot not flagged; blacklist not flagged; buy tax 0.0%, sell tax 0.0%
0xb8cf4ad387cfd607c66a207cfffc46498aacd9d6
"""

RESULT_TEXT = """
$PAIREX — 11x from our call
MC $949.1k · Liq $80.0k · 1.7h old
Called 1.4h ago at $87.9k MC (delivered token signal) · now $949.1k
0xb8cf4ad387cfd607c66a207cfffc46498aacd9d6
"""


def test_parse_call_message():
    call = parse_call_message(CALL_TEXT)
    assert call is not None
    assert call.contract_address == "0xb8cf4ad387cfd607c66a207cfffc46498aacd9d6"
    assert call.ticker == "PAIREX"
    assert call.mc_usd == 87_900
    assert call.liq_usd == 24_100
    assert call.holders == 532
    assert call.top10_pct == 38
    assert call.wallet_winrate_pct == 44.3
    assert call.wallet_realized_usd == 45_654.44
    assert call.honeypot_flagged is False
    assert call.buy_tax_pct == 0.0


def test_is_result_message():
    assert is_result_message(RESULT_TEXT) is True
    assert is_result_message(CALL_TEXT) is False


def test_parse_result_message():
    result = parse_result_message(RESULT_TEXT)
    assert result is not None
    assert result.multiplier == 11.0
    assert result.current_mc_usd == 949_100
    assert result.called_mc_usd == 87_900


if __name__ == "__main__":
    test_parse_call_message()
    test_is_result_message()
    test_parse_result_message()
    print("Semua test lolos.")
