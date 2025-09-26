
from typing import Any, List, Optional, Union, cast

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    ReplaceOrderRequest,
    StopLimitOrderRequest,
)


class AlpacaService:
    """
    Thin wrapper over alpaca-py TradingClient for live trading only.
    Never sets paper=True.
    """

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, *, raw_data: bool = False):
        # paper=False enforces LIVE per spec
        self.client = TradingClient(api_key, api_secret, paper=False, raw_data=raw_data)

    # ---- Account & Positions ----
    def get_account(self) -> Any:
        return self.client.get_account()

    def get_all_positions(self) -> Any:
        return self.client.get_all_positions()

    def get_position(self, symbol: str) -> Any | None:
        try:
            return self.client.get_open_position(symbol)
        except Exception:
            return None

    # ---- Orders ----
    def submit_limit(
        self,
        *,
        symbol: str,
        qty: Union[int, float],
        side: OrderSide,
        limit_price: float,
        tif: TimeInForce = TimeInForce.DAY,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None,
    ) -> AlpacaOrder:
        req = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            limit_price=limit_price,
            time_in_force=tif,
            extended_hours=extended_hours,
            client_order_id=client_order_id,
        )
        return self.client.submit_order(req)

    def submit_stop_limit(
        self,
        *,
        symbol: str,
        qty: Union[int, float],
        side: OrderSide,
        stop_price: float,
        limit_price: float,
        tif: TimeInForce = TimeInForce.DAY,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None,
    ) -> AlpacaOrder:
        req = StopLimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            stop_price=stop_price,
            limit_price=limit_price,
            time_in_force=tif,
            extended_hours=extended_hours,
            client_order_id=client_order_id,
        )
        return self.client.submit_order(req)

    def replace_limit(self, order_id: str, *, new_limit_price: float) -> AlpacaOrder:
        r = ReplaceOrderRequest(limit_price=new_limit_price)
        return self.client.replace_order_by_id(order_id, r)

    def cancel_order(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[AlpacaOrder]:
        params = GetOrdersRequest(status=OrderStatus.OPEN)
        raw_orders = self.client.get_orders(filter=params)
        orders = cast(List[AlpacaOrder], list(raw_orders or []))
        if symbol:
            orders = [
                o
                for o in orders
                if (getattr(o, "symbol", None) or getattr(o, "asset_symbol", None)) == symbol
            ]
        return orders

    def get_order(self, order_id: str) -> AlpacaOrder:
        return self.client.get_order_by_id(order_id)
