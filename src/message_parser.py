"""
Parser untuk 2 format pesan di Intel Hood by Vantis:

1. CALL message (diawali emoji lup, mis. "SMART MONEY"):
   $TICKER — <tag>
   MC $87.9k · Liq $24.1k · 19m old
   5m ▲49% · 1h ▲116% · 6h ▲116% · 24h ▲116%
   Vol 1h $190.1k · 24h $190.1k · 1,609 buys / 1,193 sells
   Holders 532 · reported top-10 38% · legit 43 degen
   ...
   Reported wallet stats: win 44.3% · 787 tokens · realized +$45,654.44
   ...
   Current audit: honeypot not flagged; blacklist not flagged; buy tax 0.0%, sell tax 0.0%
   0x<contract address>

2. RESULT message ("Nx from our call"):
   $TICKER — 11x from our call
   MC $949.1k · Liq $80.0k · 1.7h old
   Called 1.4h ago at $87.9k MC ... now $949.1k
   0x<contract address>

Kalau format channel berubah, cuma file ini yang perlu disesuaikan --
modul lain (filter_engine, paper_trader, dst) tidak tersentuh karena
mereka hanya bergantung pada dict/objek terstruktur yang dikembalikan
fungsi-fungsi di bawah.
"""
import re
from dataclasses import dataclass
from typing import Optional

CONTRACT_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
TICKER_RE = re.compile(r"\$([A-Za-z0-9]+)\s*[—-]")
MULTIPLIER_RESULT_RE = re.compile(r"(\d+(?:\.\d+)?)x from our call", re.IGNORECASE)

MC_RE = re.compile(r"MC\s*\$([\d,.]+)([kKmM]?)")
LIQ_RE = re.compile(r"Liq\s*\$([\d,.]+)([kKmM]?)")
AGE_RE = re.compile(r"·\s*([\d.]+)\s*([smhd])\s*old")
CHANGE_1H_RE = re.compile(r"1h\s*[▲▼]?(-?[\d,.]+)%")
CHANGE_6H_RE = re.compile(r"6h\s*[▲▼]?(-?[\d,.]+)%")
CHANGE_24H_RE = re.compile(r"24h\s*[▲▼]?(-?[\d,.]+)%")
VOL_1H_RE = re.compile(r"Vol 1h\s*\$([\d,.]+)([kKmM]?)")
BUYS_SELLS_RE = re.compile(r"([\d,]+)\s*buys\s*/\s*([\d,]+)\s*sells")
HOLDERS_RE = re.compile(r"Holders\s*([\d,]+)")
TOP10_RE = re.compile(r"top-10\s*([\d.]+)%")
WALLET_WINRATE_RE = re.compile(r"win\s*([\d.]+)%")
WALLET_REALIZED_RE = re.compile(r"realized\s*([+-]?)\$([\d,.]+)")
TAG_RE = re.compile(r"—\s*([A-Z ]+?)\n")
HONEYPOT_RE = re.compile(r"honeypot\s+(not\s+flagged|flagged)", re.IGNORECASE)
BUY_TAX_RE = re.compile(r"buy tax\s*([\d.]+)%")
SELL_TAX_RE = re.compile(r"sell tax\s*([\d.]+)%")
CALLED_MC_RE = re.compile(r"[Cc]alled.*?at\s*\$([\d,.]+)([kKmM]?)\s*MC", re.DOTALL)


def _to_usd(number_str: str, suffix: str) -> float:
    value = float(number_str.replace(",", ""))
    mult = {"k": 1_000, "m": 1_000_000}.get(suffix.lower(), 1)
    return value * mult


def _to_hours(value: str, unit: str) -> float:
    value = float(value)
    factor = {"s": 1 / 3600, "m": 1 / 60, "h": 1, "d": 24}[unit]
    return value * factor


@dataclass
class ParsedCall:
    contract_address: str
    ticker: Optional[str]
    tag: Optional[str]
    mc_usd: Optional[float]
    liq_usd: Optional[float]
    age_hours: Optional[float]
    change_1h_pct: Optional[float]
    change_6h_pct: Optional[float]
    change_24h_pct: Optional[float]
    vol_1h_usd: Optional[float]
    buys: Optional[int]
    sells: Optional[int]
    holders: Optional[int]
    top10_pct: Optional[float]
    wallet_winrate_pct: Optional[float]
    wallet_realized_usd: Optional[float]
    honeypot_flagged: Optional[bool]
    buy_tax_pct: Optional[float]
    sell_tax_pct: Optional[float]
    raw_text: str


@dataclass
class ParsedResult:
    contract_address: str
    ticker: Optional[str]
    multiplier: float
    current_mc_usd: Optional[float]
    called_mc_usd: Optional[float]
    raw_text: str


def is_result_message(text: str) -> bool:
    return bool(MULTIPLIER_RESULT_RE.search(text))


def parse_call_message(text: str) -> Optional[ParsedCall]:
    """Parse pesan call (🔎). Return None kalau tidak ada contract address."""
    contract_match = CONTRACT_RE.search(text)
    if not contract_match:
        return None

    def grp(pattern, group=1, cast=str, default=None):
        m = pattern.search(text)
        if not m:
            return default
        try:
            return cast(m.group(group))
        except (ValueError, TypeError):
            return default

    mc = MC_RE.search(text)
    liq = LIQ_RE.search(text)
    age = AGE_RE.search(text)
    vol = VOL_1H_RE.search(text)
    bs = BUYS_SELLS_RE.search(text)
    wallet_realized = WALLET_REALIZED_RE.search(text)
    honeypot = HONEYPOT_RE.search(text)
    ticker = TICKER_RE.search(text)
    tag = TAG_RE.search(text)

    return ParsedCall(
        contract_address=contract_match.group(0),
        ticker=ticker.group(1) if ticker else None,
        tag=tag.group(1).strip() if tag else None,
        mc_usd=_to_usd(*mc.groups()) if mc else None,
        liq_usd=_to_usd(*liq.groups()) if liq else None,
        age_hours=_to_hours(*age.groups()) if age else None,
        change_1h_pct=grp(CHANGE_1H_RE, cast=lambda v: float(v.replace(",", ""))),
        change_6h_pct=grp(CHANGE_6H_RE, cast=lambda v: float(v.replace(",", ""))),
        change_24h_pct=grp(CHANGE_24H_RE, cast=lambda v: float(v.replace(",", ""))),
        vol_1h_usd=_to_usd(*vol.groups()) if vol else None,
        buys=int(bs.group(1).replace(",", "")) if bs else None,
        sells=int(bs.group(2).replace(",", "")) if bs else None,
        holders=grp(HOLDERS_RE, cast=lambda v: int(v.replace(",", ""))),
        top10_pct=grp(TOP10_RE, cast=float),
        wallet_winrate_pct=grp(WALLET_WINRATE_RE, cast=float),
        wallet_realized_usd=(
            float(wallet_realized.group(2).replace(",", "")) * (-1 if wallet_realized.group(1) == "-" else 1)
            if wallet_realized
            else None
        ),
        honeypot_flagged=(honeypot.group(1).lower() == "flagged") if honeypot else None,
        buy_tax_pct=grp(BUY_TAX_RE, cast=float),
        sell_tax_pct=grp(SELL_TAX_RE, cast=float),
        raw_text=text,
    )


def parse_result_message(text: str) -> Optional[ParsedResult]:
    """Parse pesan hasil ('Nx from our call')."""
    contract_match = CONTRACT_RE.search(text)
    mult_match = MULTIPLIER_RESULT_RE.search(text)
    if not contract_match or not mult_match:
        return None

    ticker = TICKER_RE.search(text)
    mc = MC_RE.search(text)
    called_mc = CALLED_MC_RE.search(text)

    return ParsedResult(
        contract_address=contract_match.group(0),
        ticker=ticker.group(1) if ticker else None,
        multiplier=float(mult_match.group(1)),
        current_mc_usd=_to_usd(*mc.groups()) if mc else None,
        called_mc_usd=_to_usd(*called_mc.groups()) if called_mc else None,
        raw_text=text,
    )
