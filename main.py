import datetime
import requests
from fastapi import FastAPI
from bs4 import BeautifulSoup

app = FastAPI()

BONBAST_URL = "https://www.bonbast.com"


def crawl_soup(url: str) -> BeautifulSoup:
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to get {url}")
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    return soup


@app.get("/historical/{currency}")
def read_historical_currency(currency: str, date: str = datetime.date.today().strftime("%Y/%m")):
    date = datetime.datetime.strptime(date, "%Y/%m")
    soup = crawl_soup(BONBAST_URL + f"/historical/{currency}/" + date.strftime('%Y/%m'))
    table_soup = soup.find('table')
    table = [[td.text for td in tr.findAll("td")] for tr in table_soup.findAll('tr')[1:]]
    return {
        row[0]: {
            'sell': int(row[1]),
            'buy': int(row[2]),
        }
        for row in table
    }
