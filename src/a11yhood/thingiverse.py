import datetime
from operator import methodcaller
import os
from pathlib import Path
import dotenv
import pandas
from platformdirs import user_data_dir
import requests
from toolz.curried import compose

from a11yhood.utils import new_logger, new_typer

target = Path(
    user_data_dir("a11yhood", "thingiverse", datetime.date.today().isoformat()),
    "thingiverse-at.parquet",
)

HERE = Path(locals().get("__file__") or "").parent
dotenv.load_dotenv(HERE / ".env")

logger = new_logger(__name__)

params = dict(access_token=os.environ["THINGIVERSE_ACCESS_TOKEN"])


def get_terms(term="assistive+technology"):
    return requests.get(
        f"https://api.thingiverse.com/search/{term}",
        params | dict(per_page=30, page=1, type="thing"),
    )


def get_tags(term="assistive_technology"):
    return requests.get(
        f"https://api.thingiverse.com/search/{term}",
        params | dict(per_page=30, page=1, type="thing"),
    )


def get_tidy_responses(*responses):
    df = pandas.concat(
        list(map(compose(pandas.DataFrame, methodcaller("json")), responses))
    )
    data = df["hits"].apply(pandas.Series).set_index("id")
    data.tags = (
        data.tags.explode()
        .apply(pandas.Series)
        .tag.groupby(pandas.Grouper(level=0))
        .agg(list)
    )
    return data


def main_things():
    return get_tidy_responses(get_tags())


def main(target: Path = target):
    df = main_things()
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target)
    logger.debug(f"""created {target} with {len(df)} entries""")


def _typer():
    return new_typer(main, name="thingiverse")


if __name__ == "__main__":
    _typer()()
