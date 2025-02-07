from anyio import run
from numpy import isin
import dotenv, pandas, os
from pathlib import Path
import datetime

from platformdirs import user_data_dir

from a11yhood.utils import new_logger, new_typer

logger = new_logger(__name__)
target = Path(user_data_dir("a11yhood", "github", datetime.date.today().isoformat()), "github-at.parquet")  

HERE = Path(locals().get("__file__") or "").parent
dotenv.load_dotenv(HERE / ".env")
client = __import__("python_graphql_client").GraphqlClient(
    "https://api.github.com/graphql",
    dict(Authorization=f"token {os.environ['GITHUB_TOKEN']}"),
)


async def search_one(query, after=None):
    return await client.execute_async(
        """
{
      search(query: "%s", type: REPOSITORY, first: 50, after: %s) {
        repositoryCount
    wikiCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        ... on Repository {
          url
          id
          stargazerCount
          forkCount
          description
          issues {
            totalCount
          }
            languages(first: 20) {
            nodes {
              name
            }
            }
          fundingLinks {
            platform
            url
          }      
          pullRequests {
            totalCount
          }
          updatedAt
          object(expression: "HEAD:README.md") {
            ... on Blob {
              text
            }
          }
          repositoryTopics(first: 20) {
            edges {
              node {
                topic {
                  name
                }
              }
            }
          }
        }
      }
    }
      }
    }
"""
        % (query, str(after and f'"{after}"' or "null"))
    )


async def search(query, stop=20):
    """[paginate through a search results](https://til.simonwillison.net/github/graphql-pagination-python) and collect the results."""

    queries = [await search_one(query)]
    ct = 1
    while queries[-1]["data"]["search"]:
        if info := queries[-1]["data"]["search"].get("pageInfo"):
            if info["hasNextPage"]:
                logger.debug(queries[-1]["data"]["search"]["pageInfo"]["endCursor"])
                queries.append(
                    await search_one(
                        query, queries[-1]["data"]["search"]["pageInfo"]["endCursor"]
                    )
                )
                logger.debug(f"done {ct}")
                ct += 1
                if ct >= stop:
                    break
                continue
        break
    return queries


async def gather():
    from operator import itemgetter

    df = pandas.DataFrame(results := await search("topic:assistive-technology", 1))
    data = (
        df["data"]
        .apply(pandas.Series)["search"]
        .apply(pandas.Series)["edges"]
        .explode()
        .apply(pandas.Series)["node"]
        .apply(pandas.Series)
        .set_index("id")
    )
    data.pullRequests = data.pullRequests.dropna().apply(itemgetter("totalCount"))
    data.issues = data.issues.apply(itemgetter("totalCount"))
    data = data.join(
        data.pop("object").dropna().apply(itemgetter("text")).rename("README")
    )

    data = data.join(
        data.pop("repositoryTopics")
        .apply(pandas.Series)["edges"]
        .explode()
        .dropna()
        .apply(itemgetter("node"))
        .apply(itemgetter("topic"))
        .apply(itemgetter("name"))
        .groupby(level=0)
        .agg(list)
        .rename("topics")
    )
    data = data.join(
        data.pop("languages").apply(itemgetter("nodes"))
        .explode()
        .dropna()
        .apply(itemgetter("name"))
        .groupby(pandas.Grouper(level=0))
        .agg(list)
    )
    data.languages = data.languages.apply(
        lambda x: x if isinstance(x, list) else []
    )
    # theres a schema problemw when reading languages
    # we'll probably export multiple parquet files
    return data.reset_index().drop(["languages", "id"], axis=1)


def main(target: Path = target):
    df = run(gather)
    logger.debug(type(df))
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target )
    logger.debug(f"""created {target} with {len(df)} entries""")


def _typer():
    return new_typer(main, name="github")


if __name__ == "__main__":
    _typer()()
