from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .application import run_monitor
from .config import Config, ConfigError, default_config_path, load_config
from .demo import DemoMonitor
from .monitor import NodeMonitor
from .service_control import StartError, ensure_service_started


DEMO_STATES = ("starting", "syncing", "ready", "degraded", "stopped")


def monitor_parser(prog: str, *, include_demo: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--config", type=Path, default=default_config_path())
    if include_demo:
        parser.add_argument("--demo", choices=DEMO_STATES)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--ascii", action="store_true", dest="force_ascii")
    return parser


def status_parser() -> argparse.ArgumentParser:
    return monitor_parser("zakura-status", include_demo=True)


def run_configured_monitor(config: Config, args: argparse.Namespace) -> int:
    return run_monitor(
        NodeMonitor(config),
        network=config.network,
        storage_mode=config.storage_mode,
        refresh_seconds=config.refresh_seconds,
        once=args.once,
        no_color=args.no_color,
        force_ascii=args.force_ascii,
    )


def status_main(argv: Sequence[str] | None = None) -> int:
    args = status_parser().parse_args(argv)
    try:
        if args.demo:
            return run_monitor(
                DemoMonitor(args.demo),
                network="Mainnet",
                storage_mode="pruned",
                refresh_seconds=2.0,
                once=args.once,
                no_color=args.no_color,
                force_ascii=args.force_ascii,
            )
        return run_configured_monitor(load_config(args.config), args)
    except ConfigError as error:
        print(f"zakura-status: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"zakura-status: {error}", file=sys.stderr)
        return 1


def start_main(argv: Sequence[str] | None = None) -> int:
    args = monitor_parser("zakura-start", include_demo=False).parse_args(argv)
    try:
        config = load_config(args.config)
        ensure_service_started(config)
        return run_configured_monitor(config, args)
    except ConfigError as error:
        print(f"zakura-start: {error}", file=sys.stderr)
        return 2
    except StartError as error:
        print(f"zakura-start: {error}", file=sys.stderr)
        return 3
    except Exception as error:
        print(f"zakura-start: {error}", file=sys.stderr)
        return 1
