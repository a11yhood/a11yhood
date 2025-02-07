import logging
import sys


def new_typer(*funcs, **kwargs):
    from typer import Typer

    app = Typer(
        **kwargs,
        add_completion=False,
        context_settings={"help_option_names": ["-h", "--help"]},
        pretty_exceptions_enable=False,
    )
    if len(funcs) == 1:
        app.callback(invoke_without_command=True)(*funcs)
    for i, func in enumerate(funcs):
        app.command()(func)
    return app


def new_logger(name):
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.debug = logger.info = print
    return logger