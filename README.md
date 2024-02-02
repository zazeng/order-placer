# Binance Spot Order placer
This cli application places list of orders as soon as possible on the Binance spot market. A throttler is implemented in `src/cex/core/throttler.py`to prevent ip from being banned. Order placement code can be found in `src/cex/binance/order.py`

## Setup and Install
Clone the project and enter the project dir.
```
git clone https://github.com/zazeng/order-placer.git && cd order-placer
```
Ensure python version >= 3.10
```
$ python --version
```
Activate virtual env, update pip, install wheel
```
$ python -m venv venv  
$ source venv/bin/activate
$ pip install --upgrade pip && pip install dist/order_placer-1.0.0-py3-none-any.whl
```

## Run
Run the cli within the virtual enviroment created above. 
The default enviroment variables provided in `.env` file should allow for a successful run using **Mock endpoint**.

**Dry run**
```
$ order-placer ./data/Orders.csv ./data/Precision.csv
```
**Execute**
```
$ order-placer ./data/Orders.csv ./data/Precision.csv --exec
```

**Execute simulate failed order request**
```
$ order-placer ./data/Orders.csv ./data/Precision.csv --exec --mock-fail-rate 0.01
```
## Enviroment variables
Defined in `.env` file. Expected variables are **APP_ENV**, **BNCE_API_KEYS** and **BNCE_SECRET_KEYS**


#### **APP_ENV**
Defines how the application will run. Valid values: test, dev

test: No network connection will be made. A *Mock* endpoint will be used. 

dev: Network connection will be made to the binance testnet.

#### **BNCE_API_KEYS**
Api keys for binance endpoint, white space seperated. Format: 

`"{account id 1}:{api key 1} {account id 2}:{api key 2}"`

#### **BNCE_SECRET_KEYS**
Secret keys for binance endpoint, white space seperated. Format: 

`"{account id 1}:{secret key 1} {account id 2}:{secret key 2}"`
## Assumptions
- Only GTC limit orders for spot pairs are placed.
- Application is programed against Binance spot endpoint.
- Not atomic. ie. failed order does not cancel existing successful ones
- "At most once" semantics for order placement
- No retries for requests required (regardles of http status)

## TODO 
- More robust dry run validation. get tick size, min order size from api and validate with csv.
- More robust rate limiting by retriving rate limits from endpoint and by incorporating x-ratelimit-* headers.
- Implement exponential retry for suitable http error
