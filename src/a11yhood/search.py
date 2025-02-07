import atexit
from pathlib import Path

import dotenv
import pandas

from a11yhood.utils import new_logger, new_typer
from . import github, ravelry, thingiverse

HERE = Path(locals().get("__file__") or "").parent
dotenv.load_dotenv(HERE / ".env")

logger = new_logger(__name__)


def align_data():
    import polars

    g, r, t = (
        polars.read_parquet(github.target, allow_missing_columns=True),
        polars.read_parquet(ravelry.target, allow_missing_columns=True),
        polars.read_parquet(thingiverse.target),
    )

    return polars.concat(
        [
            g[["url", "README"]].rename({"README": "description"}),
            g[["url", "description"]],
            ("https://www.ravelry.com/patterns/library/" + r["permalink"])
            .rename("url")
            .to_frame()
            .with_columns(description=r["notes"]),
        ]
    )


def new_duckdb_connection(df):
    import duckdb

    atexit.register((connection := duckdb.connect(read_only=False)).close)
    connection.register("documents_df", df)
    connection.execute(
        """
    SET scalar_subquery_error_on_multiple_rows = false;
    CREATE TABLE documents AS (SELECT * FROM documents_df);
    """
    )

    connection.execute(
        """
    PRAGMA create_fts_index('documents', 'url', 'description', stopwords='english');
    """
    )

    connection.execute(
        """
    PREPARE fts_query AS (
        WITH scored_docs AS (
            SELECT *, fts_main_documents.match_bm25(url, ?) AS score FROM documents)
        SELECT url, description
        FROM scored_docs
        WHERE score IS NOT NULL
        ORDER BY score DESC
        LIMIT 10)
    """
    )

    return connection


def search(q: str, *, db={}):
    if not db:
        db = db.setdefault("fts", new_duckdb_connection(align_data()))

    else:
        db = db["fts"]

    df = pandas.DataFrame(
        db.execute("EXECUTE fts_query('" + q + "')").fetchall(),
        None,
        "url description".split(),
    )
    df = df.set_index("url")
    return df.description.to_frame()


def main(q: str):
    print(search(q).to_markdown())


def widget():
    import ipywidgets

    @ipywidgets.interact
    def app(text: str = "hat"):
        return ipywidgets.HTML(search(text).style._repr_html_())

    return app


def _typer():
    return new_typer(main, name="search")


if __name__ == "__main__":
    _typer()()
