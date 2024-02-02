from enum import Enum


class BnceOrderType(str, Enum):
    """Only limit order supported"""

    LIMIT = "LIMIT"


class BnceOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class BnceOrderTimeInForce(str, Enum):
    """Only GTC is supported"""

    GOOD_TILL_CANCEL = "GTC"
