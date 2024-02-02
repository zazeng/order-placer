import asyncio
import csv
from decimal import Decimal
import logging
import os
from time import perf_counter_ns

import aiohttp

from order_placer.cex.binance.mock import MockBnceRestEndpointV3
from order_placer.cex.binance.rest_endpoint import (
    BnceRestEndpointV3,
    BnceOrderSide,
    BnceOrderType,
    BnceOrderTimeInForce,
)



BNCE_REST_ENDPOINT = "https://api.binance.com"
BNCE_TESTNET = "https://testnet.binance.vision"
BNCE_MOCK_ENDPOINT = "https://mock.binance.com"
SYMBOL_SCALE = {"JTOUSDT": 8}  # obtained from /exchangeInfo


class BnceSpotLimitOrderPlacer:
    def __init__(
        self, account_metadata: dict, orders_fp: str, mock_failure_rate: float = 0.0
    ) -> None:
        self._account = account_metadata
        self._orders_fp = orders_fp
        self._mock_failure_rate = mock_failure_rate
        self._endpoint_url = None
        self._env = os.environ.get("APP_ENV")
        self._sess = None

        if self._env == "dev":
            self._sess = aiohttp.ClientSession(BNCE_TESTNET)
        elif self._env == "test":
            self._sess = aiohttp.ClientSession(BNCE_MOCK_ENDPOINT)
        else:
            self._sess = aiohttp.ClientSession(BNCE_REST_ENDPOINT)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._sess.close()

    def _make_endpoint(
        self, api_key: str | None = None, secret_key: str | None = None
    ) -> BnceRestEndpointV3 | MockBnceRestEndpointV3:
        """Returns Mock endpoint if env is 'test' else real endpoint"""
        if self._env == "test":
            return MockBnceRestEndpointV3(
                self._sess, api_key, secret_key, self._mock_failure_rate
            )
        return BnceRestEndpointV3(self._sess, api_key, secret_key)

    async def execute(self):
        """Place orders in `self._orders_fp`"""
        start_time_ns = perf_counter_ns()
        logging.info("Starting order execution")
        account_ids = list(self._account.keys())
        endpoints = {
            i: self._make_endpoint(
                self._account[i]["api_key"],
                self._account[i]["secret_key"],
            )
            for i in account_ids
        }
        order_tasks = set()
        orders = []

        # prepare tasks for concurrent request.
        with open(self._orders_fp, "r") as f:
            reader = csv.DictReader(f, delimiter=",")
            for idx, row in enumerate(reader):
                if row["Direction"].lower() == "buy":
                    side = BnceOrderSide.BUY
                elif row["Direction"].lower() == "sell":
                    side = BnceOrderSide.SELL
                else:
                    raise ValueError(f"Invalid direction detected: {row['Direction']}")
                q = Decimal(10) ** -SYMBOL_SCALE[row["Pair"]]
                row["Quantity"] = Decimal(row["Quantity"]).quantize(q)
                row["Price"] = (Decimal(row["Price"]).quantize(q),)
                orders.append(row)
                order_tasks.add(
                    asyncio.create_task(
                        endpoints[int(row["Account"])].post_order(
                            symbol=row["Pair"],
                            qty=row["Quantity"],
                            price=row["Price"],
                            side=side,
                            type=BnceOrderType.LIMIT,
                            time_in_force=BnceOrderTimeInForce.GOOD_TILL_CANCEL,
                        ),
                        name=idx,
                    )
                )

        successful_orders: list[
            (int, dict)
        ] = []  # list of (order idx, exchange response)

        # start sending orders concurrently
        try:
            while order_tasks:
                done, order_tasks = await asyncio.wait(
                    order_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    res: aiohttp.ClientResponse
                    try:
                        res = task.result()
                    except Exception as e:
                        # non http errors. all pending tasks are cancelled
                        # TODO use task.name as idx to retrieve original params from orders list and display
                        logging.exception(
                            f" Exception encountered while sending order {orders[int(task.get_name())]}. {e}"
                        )
                        raise e
                    else:
                        # status 200
                        if res.ok:
                            data = await res.json()
                            if "code" in data:
                                # sometimes exchange error is present despite status 200
                                # https://github.com/binance/binance-spot-api-docs/blob/master/errors.md
                                logging.exception(
                                    f"Exchange error, cancelling pending tasks. code: {data['code']}, msg: {data['msg']}"
                                )
                                raise Exception("Exchange error: error: {data}")
                            else:
                                # success
                                successful_orders.append(data)
                                logging.info(
                                    f"Placed order: {orders[int(task.get_name())]}. resp: {data}"
                                )
                        else:
                            # cancel on http errors
                            error = await res.json()
                            logging.exception(
                                f" Http error encountered while placing order. status: {res.status}, reason: {res.reason}, error: {error}, order: {orders[int(task.get_name())]}"
                            )
                            res.raise_for_status()
        finally:
            stop_time_ns = perf_counter_ns()
            logging.info(
                f"Placed {len(successful_orders)}/{len(orders)} orders in {(stop_time_ns - start_time_ns) / 1000000} ms."
            )
            # TODO make request to endpoint to validate placed orders

    async def dry_run(self):
        """Performs validation of credentials in `self._account` and orders in `self._orders_fp` and"""
        logging.info("Starting dry run.")
        invalid_credentials = []

        async with aiohttp.ClientSession() as sess:
            # validate credentials, retrieve account balance
            logging.info("Validating credentials")
            cred_tasks = []
            acc_idx = []

            for acc_id, acc_info in self._account.items():
                endpoint = self._make_endpoint(
                    api_key=acc_info["api_key"],
                    secret_key=acc_info["secret_key"],
                )
                cred_tasks.append(endpoint.get_account_info())
                acc_idx.append(acc_id)

            cred_resp = await asyncio.gather(*cred_tasks)
            for i, resp in enumerate(cred_resp):
                if resp.status in (401, 403):
                    logging.error(
                        f"Invalid credentials for account id: {acc_idx[i]} status: {resp.status} reason: {resp.reason}"
                    )
                    invalid_credentials.append(acc_idx[i])
                    continue
                else:
                    resp.raise_for_status()

            if invalid_credentials:
                raise ValueError(
                    f"Invalid credentials detected for accounts: {invalid_credentials}"
                )
            logging.info(
                f"Successfully validated credentials from accounts: {list(self._account.keys())}"
            )

            #  retrieve valid spot instruments
            logging.info("Retrieving valid spot symbols")
            endpoint = self._make_endpoint()
            resp = await endpoint.get_symbols()
            resp.raise_for_status()
            data = await resp.json()
            spot_instruments = set((rec["symbol"] for rec in data["symbols"]))

        # validate orders
        logging.info("Validating Orders")
        invalid_orders = []

        with open(self._orders_fp, "r") as f:
            reader = csv.DictReader(f, delimiter=",")
            norders = 0
            for i, row in enumerate(reader):
                norders += 1
                errors = []

                # check symbol in valid symbols
                if row["Pair"] not in spot_instruments:
                    errors.append("Invalid Pair")
                # check direction is valid
                if row["Direction"].lower() not in ("buy", "sell"):
                    errors.append("Invalid Direction")
                # check price and quantity are present
                if (
                    row["Price"] is None
                    or row["Quantity"] is None
                    or Decimal(row["Price"]) <= Decimal(0)
                    or Decimal(row["Quantity"]) <= Decimal(0)
                ):
                    errors.append("Invalid price or quantity")

                if errors:
                    invalid_orders.append((i, row, errors))

            if invalid_orders:
                logging.error("Invalid orders detected:")
                for i, row, errors in invalid_orders:
                    logging.error(f"row number: {i + 1}, row: {row}, errors: {errors}")
            else:
                logging.info(f"Succesfully validated {norders} orders")
