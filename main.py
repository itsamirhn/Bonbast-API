import contextlib
import datetime

import httpx
from bonbast.server import get_prices_from_api, get_token_from_main_page
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

app = FastAPI()

FastAPICache.init(InMemoryBackend())

BONBAST_URL = "https://www.bonbast.com"

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)


def merge_and_extract_tables(tables_soup):
    tables = []
    for table_soup in tables_soup:
        for tr in table_soup.find_all("tr")[1:]:
            table = [td.text for td in tr.find_all("td")]
            tables.append(table)
    return tables

def crawl_soup(url: str, post_data: dict) -> BeautifulSoup:
    response = httpx.post(url, data=post_data)
    if response.status_code != 200:
        raise Exception(f"Failed to crawl {url}")
    html = response.text
    return BeautifulSoup(html, 'html.parser')


@app.get("/historical/{currency}")
@cache(expire=60 * 60 * 24)
async def read_historical_currency(currency: str, date: str = datetime.date.today().strftime("%Y-%m")):
    try:
        date = datetime.datetime.strptime(date, "%Y-%m")
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="Invalid Date format. Expected YYYY-MM"
        ) from err
    soup = crawl_soup(
        f"{BONBAST_URL}/historical",
        {"date": date.strftime("%Y-%m-%d"), "currency": currency},
    )
    table_soup = soup.find("table")
    table = [[td.text for td in tr.findAll("td")]
             for tr in table_soup.findAll("tr")[1:]]
    prices = {}
    for row in table:
        with contextlib.suppress(ValueError):
            exact_date = row[0]
            sell, buy = int(row[1]), int(row[2])
            if sell > 0 and buy > 0:
                prices[exact_date] = {
                    "sell": sell,
                    "buy": buy
                }
    return prices


@app.get("/archive/")
@cache(expire=60 * 60 * 24)
async def read_archive(date: str = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")):
    try:
        date = datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="Invalid Date format. Expected YYYY-MM-DD"
        ) from err

    soup = crawl_soup(
        f"{BONBAST_URL}/archive", {"date": date.strftime("%Y-%m-%d")}
    )
    table_soup = soup.find_all("table")
    table = merge_and_extract_tables(table_soup[:-1])
    prices = {"date": date.strftime("%Y-%m-%d")}
    for row in table:
        with contextlib.suppress(ValueError):
            currency = row[0].lower()
            sell, buy = int(row[2]), int(row[3])
            if sell > 0 and buy > 0:
                prices[currency] = {
                    "sell": sell,
                    "buy": buy
                }
    return prices


@app.get("/latest/currencies")
@cache(expire=60 * 30)
async def read_latest():
    token = get_token_from_main_page()
    currencies, _, _ = get_prices_from_api(token)
    return {c.code.lower(): {"sell": c.sell, "buy": c.buy} for c in currencies}


@app.get("/latest/coins")
@cache(expire=60 * 30)
async def read_latest():
    token = get_token_from_main_page()
    _, coins, _ = get_prices_from_api(token)
    return {c.code.lower(): {"sell": c.sell, "buy": c.buy} for c in coins}


@app.get("/archive/range")
@cache(expire=60 * 60 * 24)
async def read_archive_range(
        start_date: str,
        end_date: str = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")):
    try:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as err:
        raise HTTPException(
            status_code=422, detail="Invalid Date format. Expected YYYY-MM-DD"
        ) from err

    price_range = {}
    duration = end_date - start_date

    for i in range(duration.days + 1):
        day = start_date + datetime.timedelta(days=i)
        price = await read_archive(day.strftime("%Y-%m-%d"))
        date = price.pop("date")
        price_range[date] = price
    return price_range

