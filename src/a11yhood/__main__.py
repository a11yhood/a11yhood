import datetime
from pathlib import Path
from anyio import run
from platformdirs import user_data_dir
import typer
from .github import _typer as github_app
from .ravelry import _typer as ravelry_app

target = Path(user_data_dir("a11yhood", "github", datetime.date.today().isoformat()))
app = typer.Typer(
    name="a11yhood", context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False
)

app.add_typer(scraper := typer.Typer(name="scraper"))
scraper.add_typer(github_app())
scraper.add_typer(ravelry_app())

if __name__ == "__main__":
    app()
