import datetime

import requests
from bonbast.server import get_prices_from_api, get_token_from_main_page
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

app = FastAPI()

BONBAST_URL = "https://www.bonbast.com"

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)


def crawl_soup(url: str) -> BeautifulSoup:
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to get {url}")
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    return soup


@app.get("/historical/{currency}")
@cache(expire=60 * 60 * 24)
async def read_historical_currency(currency: str, date: str = datetime.date.today().strftime("%Y-%m")):
    try:
        date = datetime.datetime.strptime(date, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid Date format. Expected YYYY-MM")

    soup = crawl_soup(BONBAST_URL + f"/historical/{currency}/" + date.strftime("%Y/%m"))
    table_soup = soup.find("table")
    table = [[td.text for td in tr.findAll("td")] for tr in table_soup.findAll("tr")[1:]]
    prices = {}
    for row in table:
        try:
            exact_date = row[0]
            sell, buy = int(row[1]), int(row[2])
            if sell > 0 and buy > 0:
                prices[exact_date] = {
                    "sell": sell,
                    "buy": buy
                }
        except ValueError:
            pass
    return prices


@app.get("/archive/")
@cache(expire=60 * 60 * 24)
async def read_archive(date: str = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")):
    try:
        date = datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid Date format. Expected YYYY-MM-DD")

    soup = crawl_soup(BONBAST_URL + "/archive" + date.strftime("/%Y/%m/%d"))
    table_soup = soup.find("table")
    table = [[td.text for td in tr.findAll("td")] for tr in table_soup.findAll("tr")[1:]]
    prices = {"date": date.strftime("%Y-%m-%d")}
    for row in table:
        try:
            currency = row[0].lower()
            sell, buy = int(row[2]), int(row[3])
            if sell > 0 and buy > 0:
                prices[currency] = {
                    "sell": sell,
                    "buy": buy
                }
        except ValueError:
            pass
    return prices


@app.get("/latest")
@cache(expire=60 * 30)
async def read_latest():
    token = get_token_from_main_page()
    currencies, _, _ = get_prices_from_api(token)
    prices = {c.code.lower(): {"sell": c.sell, "buy": c.buy} for c in currencies}
    return prices


@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend())
