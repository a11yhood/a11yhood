import datetime
from pathlib import Path
from anyio import run
from platformdirs import user_data_dir
import typer

target = Path(user_data_dir("a11yhood", "github", datetime.date.today().isoformat()))
app = typer.Typer(
    name="a11yhood", context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False
)

app.add_typer(scraper := typer.Typer(name="scraper"))


@scraper.command()
def github(target: Path = target / "github"):
    import importnb

    # with importnb.Notebook():
    from . import gh
    print("start github scraper")
    run(gh.main, target)
    return


if __name__ == "__main__":
    app()
