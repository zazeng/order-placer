#!/usr/bin/env python

import argparse
import asyncio
from collections import defaultdict
import csv
import logging
import os

from dotenv import load_dotenv

from order_placer.cex.binance.order import BnceSpotLimitOrderPlacer

logging.basicConfig(level=logging.DEBUG)


async def _start_app(exec: bool, account_metadata: dict, orders_fp: str, mock_fail_rate: float):
    async with BnceSpotLimitOrderPlacer(account_metadata, orders_fp, mock_fail_rate) as app:
        if exec:
            await app.execute()
        else:
            await app.dry_run()


def main():
    parser = argparse.ArgumentParser(
        prog="order",
        description="place orders provided in csv file on bitmex exchange",
    )
    parser.add_argument("orders_fp", help="filepath for orders data", type=str)
    parser.add_argument("precision_fp", help="filepath for precision data", type=str)
    parser.add_argument(
        "-e",
        "--exec",
        action="store_true",
        help="if flag is present run in execution mode else run in dry run mode",
    )
    parser.add_argument(
        "--mock-fail-rate",
        default=0,
        help="value between 0 and 1. how often order fails when enviroment variable APP_ENV == test",
        type=float,
    )
    args = parser.parse_args()
    load_dotenv()

    account_metadata = defaultdict(dict)

    for key_str in os.environ.get("BNCE_API_KEYS").split(" "):
        acc_id, key = key_str.split(":", maxsplit=1)
        account_metadata[int(acc_id)]["api_key"] = key

    for key_str in os.environ.get("BNCE_SECRET_KEYS").split(" "):
        acc_id, key = key_str.split(":", maxsplit=1)
        account_metadata[int(acc_id)]["secret_key"] = key

    with open(args.precision_fp, "r") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            account_metadata[int(row["Account"])]["px_prec"] = int(
                row["Price Precision"]
            )
            account_metadata[int(row["Account"])]["qty_prec"] = int(
                row["Quantity Precision"]
            )

    asyncio.run(_start_app(args.exec, account_metadata, args.orders_fp, args.mock_fail_rate))


if __name__ == "__main__":
    main()
