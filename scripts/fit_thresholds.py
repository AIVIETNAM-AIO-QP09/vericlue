"""Offline voice LTT selection; never writes deployed thresholds/configuration."""

import sys

from vericlue_ml.eval.nes2net_candidate import main

if __name__ == "__main__":
    raise SystemExit(main(["select", *sys.argv[1:]]))
