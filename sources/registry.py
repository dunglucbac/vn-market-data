"""The default source chain.

The chain is tried head-first *per capability*, so ordering is priority and a source
only needs to implement what it can actually answer. Adding a backend is one import
plus one list entry here — or, without touching the package at all,
``adapter.set_sources([MySource(), *build_sources()])``.
"""
from vn_market_data.sources.base import DataSource
from vn_market_data.sources.cafef import CafeFSource
from vn_market_data.sources.dnse import DNSESource
from vn_market_data.sources.fireant import FireAntSource
from vn_market_data.sources.kbs import KBSSource
from vn_market_data.sources.vietcap import VietcapSource
from vn_market_data.sources.vndirect import VNDirectSource


def build_sources() -> list[DataSource]:
    """The built-in chain: ``[DNSE, Vietcap, VNDirect, CafeF, KBS, FireAnt]``.

    DNSE's Entrade endpoint is open and fast, so it serves OHLCV first; it implements
    only ``get_ohlcv``, so board / statements / events fall through to Vietcap, which
    is also the OHLCV fallback. VNDirect supplies market-wide turnover, including
    put-through deals; CafeF supplies settled foreign history; KBS supplies the
    matched-trade tape; FireAnt provides a fallback for market turnover.

    Every source here is pure ``httpx``, so the chain is the same on every install.
    Until 2026-10-06 the second entry was ``VCISource`` — the same Vietcap endpoints
    through ``vnstock`` — and was dropped where that package was missing. It is still
    in the package for anyone who wants it (``set_sources``), but nothing here needs
    ``vnstock`` any more.
    """
    return [DNSESource(), VietcapSource(), VNDirectSource(), CafeFSource(), KBSSource(), FireAntSource()]
