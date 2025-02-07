# https://nbviewer.org/github/tonyfast/tonyfast/blob/main/tonyfast/xxiv/2025-01-29-ravelry.ipynb
from logging import getLogger
from operator import attrgetter, methodcaller
from pathlib import Path
from anyio import run
import dotenv
from pandas import DataFrame, Series
import pandas
from platformdirs import user_data_dir
import requests
from tomli import loads
import os
import httpx
import urllib
from toolz.curried import compose, partial, pipe, partition, do, map
import datetime

from a11yhood.utils import new_logger, new_typer

target = Path(user_data_dir("a11yhood", "ravelry", datetime.date.today().isoformat()))

HERE = Path(locals().get("__file__") or "").parent
dotenv.load_dotenv(HERE / ".env")

__import__("dotenv").load_dotenv()
auth = (os.environ["RAVELRY_USERNAME"], os.environ["RAVELRY_PASSWORD"])
searches: dict = loads(
    """adaptive.pa = "adaptive"
"medical device access".pa = "medical-device-access"
"medical device support".pa = "medical-device-accessory"
"mobility aid support".pa = "mobility-aid-accesory"
other.pa = "other-add-accessibility"
"therapy aid/toy".pa = "therapy-aid"
medical.pc = "medical" 
"""
)

logger = new_logger(__name__)


def get_seeds(searches=searches):
    return "https://api.ravelry.com/patterns/search.json?" + Series(searches).apply(
        urllib.parse.urlencode
    )


async def get_pattern_index_init(searches: dict = searches) -> DataFrame:

    first_pages = (seeds := get_seeds(searches)).apply(
        compose(
            partial(httpx.get, auth=auth),
            do(compose(logger.debug, "requesting {}".format)),
        )
    )
    status_codes = first_pages.apply(attrgetter("status_code"))
    return (
        seeds,
        first_pages,
        first_pages[status_codes.eq(200)].apply(methodcaller("json")).apply(Series),
    )


async def get_pattern_index_urls(searches=searches):
    seeds, first_pages, init = await get_pattern_index_init(searches)
    logger.debug(
        f"{get_pattern_index_urls.__name__} is generating the other api requests"
    )
    paginated = init.paginator.apply(Series)
    paginated = paginated[paginated.page_count.gt(1)].drop(columns="page")
    paginated = paginated.join(
        paginated.page_count.add(1)
        .apply(compose(list, partial(range, 2)))
        .explode()
        .rename("page")
    )
    return first_pages, seeds[paginated.index] + "&page=" + paginated.page.astype(str)


async def get_pattern_index(searches=searches) -> DataFrame:
    first_pages, other_urls = await get_pattern_index_urls(searches)
    other_pages = other_urls.apply(
        compose(
            partial(httpx.get, auth=auth),
            do(compose(logger.debug, "requesting {}".format)),
        )
    )
    return pandas.concat([first_pages, other_pages]).to_frame("response")


async def tidy_pattern_ids(responses):
    logger.debug(f"{get_pattern_index_urls.__name__} is gathering all pattern ids")
    responses = responses.assign(
        url=responses.response.apply(attrgetter("url")),
        status_code=responses.response.apply(attrgetter("status_code")),
    )
    responses = responses[responses.status_code.eq(200)]
    responses = responses.assign(
        **responses.response.apply(methodcaller("json")).apply(Series)
    )

    return (
        responses.patterns.explode()
        .apply(Series)
        .reset_index()
        .drop_duplicates("id")
        .set_index("id")
    )


async def get_patterns(pattern_ids, limit=3, *, window=50):
    pattern_urls = pipe(
        len(pattern_ids),
        range,
        partition(window),
        map(
            compose(
                "https://api.ravelry.com/patterns.json?ids={}".format,
                "+".join,
                map(compose(str, pattern_ids.index.__getitem__)),
            )
        ),
        list,
        Series,
    )

    pattern_pages = pattern_urls.iloc[:limit].apply(
        compose(
            partial(httpx.get, auth=auth),
            do(compose(logger.debug, "requesting {}".format)),
        )
    )

    return (
        pattern_pages.apply(methodcaller("json"))
        .apply(Series)
        .patterns.apply(compose(list, dict.values))
        .explode()
        .apply(Series)
    )


async def main_patterns(searches=searches) -> DataFrame:
    responses = await get_pattern_index(searches)
    pattern_ids = await tidy_pattern_ids(responses)
    return await get_patterns(pattern_ids, window=50)


def main(target: Path = target):
    df = run(main_patterns)
    target.mkdir(parents=True, exist_ok=True)
    target /= "ravelry-at.parquet"
    df.to_parquet(target)
    logger.debug(f"""created {target} with {len(df)} entries""")


def _typer():
    return new_typer(main, name="ravelry")


if __name__ == "__main__":
    _typer()()
