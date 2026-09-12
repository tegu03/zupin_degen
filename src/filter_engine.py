"""
Skoring call (0-100) untuk memperkirakan potensi 3x-10x, berdasarkan
parameter di config/settings.yaml. Semua bobot & threshold dikonfigurasi,
tidak di-hardcode, supaya bisa di-tuning tanpa ubah kode.
"""
from dataclasses import dataclass

from src.message_parser import ParsedCall


@dataclass
class FilterResult:
    score: float
    passed: bool
    reasons: list[str]


def score_call(call: ParsedCall, filter_cfg: dict) -> FilterResult:
    score = 0.0
    reasons = []
    max_score = 0.0

    # --- Market cap sweet spot ---
    w = filter_cfg["mc_sweet_spot_weight"]
    max_score += w
    if call.mc_usd is not None:
        if filter_cfg["mc_min_usd"] <= call.mc_usd <= filter_cfg["mc_max_usd"]:
            score += w
            reasons.append(f"MC ${call.mc_usd:,.0f} dalam rentang ideal (+{w})")
        else:
            reasons.append(f"MC ${call.mc_usd:,.0f} di luar rentang ideal (+0)")

    # --- Liquidity ---
    w = filter_cfg["liquidity_weight"]
    max_score += w
    if call.liq_usd is not None:
        ratio_ok = (
            call.mc_usd
            and call.liq_usd / call.mc_usd >= filter_cfg["liq_to_mc_ratio_min"]
        )
        if call.liq_usd >= filter_cfg["liq_min_usd"] and ratio_ok:
            score += w
            reasons.append(f"Liquidity sehat ${call.liq_usd:,.0f} (+{w})")
        else:
            reasons.append("Liquidity terlalu tipis relatif ke MC (+0)")

    # --- Holder / concentration ---
    w = filter_cfg["holder_weight"]
    max_score += w
    if call.holders is not None and call.top10_pct is not None:
        if (
            call.holders >= filter_cfg["holders_min"]
            and call.top10_pct <= filter_cfg["top10_concentration_max_pct"]
        ):
            score += w
            reasons.append(f"Holder {call.holders}, top10 {call.top10_pct}% aman (+{w})")
        else:
            reasons.append("Holder terlalu sedikit / konsentrasi top10 tinggi (+0)")

    # --- Activity (buy/sell ratio & volume) ---
    w = filter_cfg["activity_weight"]
    max_score += w
    if call.buys is not None and call.sells and call.mc_usd and call.vol_1h_usd is not None:
        ratio = call.buys / max(call.sells, 1)
        vol_ratio = call.vol_1h_usd / call.mc_usd
        if (
            ratio >= filter_cfg["buy_sell_ratio_min"]
            and vol_ratio >= filter_cfg["volume_to_mc_ratio_min"]
        ):
            score += w
            reasons.append(f"Buy/sell ratio {ratio:.2f}, vol/MC {vol_ratio:.2f} (+{w})")
        else:
            reasons.append(f"Momentum lemah: buy/sell {ratio:.2f}, vol/MC {vol_ratio:.2f} (+0)")

    # --- Wallet reputation ---
    w = filter_cfg["wallet_weight"]
    max_score += w
    if call.wallet_winrate_pct is not None:
        winrate_ok = call.wallet_winrate_pct >= filter_cfg["wallet_winrate_min_pct"]
        realized_ok = not filter_cfg["wallet_realized_profit_positive"] or (
            call.wallet_realized_usd is not None and call.wallet_realized_usd > 0
        )
        if winrate_ok and realized_ok:
            score += w
            reasons.append(f"Wallet winrate {call.wallet_winrate_pct}% (+{w})")
        else:
            reasons.append("Reputasi wallet sumber di bawah threshold (+0)")

    # --- Tag ---
    w = filter_cfg["tag_weight"]
    max_score += w
    if call.tag and any(t.lower() in call.tag.lower() for t in filter_cfg["preferred_tags"]):
        score += w
        reasons.append(f"Tag '{call.tag}' termasuk preferred (+{w})")

    # --- Audit ---
    w = filter_cfg["audit_weight"]
    max_score += w
    audit_ok = True
    if filter_cfg["require_no_honeypot_flag"] and call.honeypot_flagged:
        audit_ok = False
    max_tax = filter_cfg["require_buy_sell_tax_max_pct"]
    if call.buy_tax_pct is not None and call.buy_tax_pct > max_tax:
        audit_ok = False
    if call.sell_tax_pct is not None and call.sell_tax_pct > max_tax:
        audit_ok = False
    if audit_ok:
        score += w
        reasons.append(f"Audit bersih (+{w})")
    else:
        reasons.append("Audit gagal (honeypot/tax tinggi) (+0)")

    # Normalisasi ke 0-100 berdasarkan field yang benar-benar tersedia
    normalized = (score / max_score * 100) if max_score else 0.0
    passed = normalized >= filter_cfg["min_score"]

    return FilterResult(score=round(normalized, 1), passed=passed, reasons=reasons)
