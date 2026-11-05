"""
Flattrade API Broker Adapter (Pi API / Shoonya REST Protocol).
Integrates live order placement, market quotes, position books, and MIS square-off
with Flattrade's zero-brokerage infrastructure.
"""

import hashlib
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from .base import BaseBroker

class FlattradeBroker(BaseBroker):
    """
    Connects to Flattrade PiConnect REST API.
    Docs: https://flattrade.in/kosh/
    """
    BASE_URL = "https://piconnect.flattrade.in/PiConnectTP"

    def __init__(self, user_id: str, api_key: str, api_secret: str, token: Optional[str] = None):
        self.user_id = user_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.token = token
        self.is_authenticated = bool(token)

    def authenticate(self, totp_code: str) -> bool:
        """
        Authenticates with Flattrade using User ID, API Key, and TOTP.
        Computes SHA-256 hash of API key + secret.
        """
        app_key = f"{self.api_key}{self.api_secret}"
        sha256_hash = hashlib.sha256(app_key.encode('utf-8')).hexdigest()
        
        payload = {
            "uid": self.user_id,
            "actid": self.user_id,
            "apikey": self.api_key,
            "appkey": sha256_hash,
            "totp": totp_code
        }
        
        # Post request to QuickAuth
        url = f"{self.BASE_URL}/QuickAuth"
        data = f"jData={json.dumps(payload)}".encode('utf-8')
        
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_json = json.loads(resp.read().decode('utf-8'))
                if res_json.get("stat") == "Ok":
                    self.token = res_json.get("susertoken")
                    self.is_authenticated = True
                    return True
        except Exception as e:
            print(f"[FlattradeBroker] Auth Error: {e}")
        return False

    def _api_call(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generic authenticated API request to Flattrade"""
        if not self.is_authenticated and self.token is None:
            return {"stat": "Not_Ok", "emsg": "Not Authenticated"}
            
        payload["uid"] = self.user_id
        url = f"{self.BASE_URL}/{endpoint}"
        body = f"jData={json.dumps(payload)}&jKey={self.token}".encode('utf-8')
        
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {"stat": "Not_Ok", "emsg": str(e)}

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps standard order format to Flattrade PlaceOrder API:
        prd='M' for MIS (Intraday), trantype='B' (Buy) or 'S' (Sell), prctyp='LMT' or 'MKT'
        """
        side = "B" if order["side"].upper() == "BUY" else "S"
        order_type = "LMT" if "price" in order and order["price"] > 0 else "MKT"
        
        payload = {
            "actid": self.user_id,
            "exch": order.get("exchange", "NSE"),
            "tsym": order["symbol"],
            "qty": str(order["quantity"]),
            "prc": str(order.get("price", "0")),
            "prd": "M",  # MIS product code in Flattrade
            "trantype": side,
            "prctyp": order_type,
            "ret": "DAY"
        }
        
        if order.get("stop_loss"):
            payload["blprc"] = str(order["stop_loss"]) # Book-loss / Stop-Loss trigger
            
        res = self._api_call("PlaceOrder", payload)
        return res

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        payload = {
            "norenordno": order_id
        }
        return self._api_call("CancelOrder", payload)

    def modify_order(self, order_id: str, new_price: Optional[float] = None, 
                     new_quantity: Optional[int] = None, new_trigger_price: Optional[float] = None) -> Dict[str, Any]:
        payload = {
            "norenordno": order_id
        }
        if new_price is not None:
            payload["newprc"] = str(new_price)
        if new_quantity is not None:
            payload["newqty"] = str(new_quantity)
        if new_trigger_price is not None:
            payload["newtrgprc"] = str(new_trigger_price)
            
        return self._api_call("ModifyOrder", payload)

    def get_positions(self) -> List[Dict[str, Any]]:
        payload = {"actid": self.user_id}
        res = self._api_call("PositionBook", payload)
        if isinstance(res, list):
            return res
        return []

    def get_orders(self) -> List[Dict[str, Any]]:
        payload = {"actid": self.user_id}
        res = self._api_call("OrderBook", payload)
        if isinstance(res, list):
            return res
        return []

    def get_ltp(self, symbol: str) -> float:
        payload = {
            "exch": "NSE",
            "token": symbol
        }
        res = self._api_call("GetQuotes", payload)
        if "lp" in res:
            return float(res["lp"])
        return 0.0

    def square_off_all(self, reason: str = "MANUAL") -> List[Dict[str, Any]]:
        """Square off all open MIS intraday positions"""
        positions = self.get_positions()
        closed = []
        for pos in positions:
            net_qty = int(pos.get("netqty", 0))
            if net_qty != 0:
                side = "SELL" if net_qty > 0 else "BUY"
                sq_order = {
                    "symbol": pos.get("tsym"),
                    "quantity": abs(net_qty),
                    "side": side,
                    "exchange": pos.get("exch", "NSE"),
                    "product": "MIS"
                }
                res = self.place_order(sq_order)
                closed.append({"symbol": pos.get("tsym"), "result": res})
        return closed
