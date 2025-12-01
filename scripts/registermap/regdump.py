#!/usr/bin/env python3
"""
regdump.py - A simple tool to analyze register values for a given SoC.

Usage example:
    ./regump.py -s imx8 -i ./input -o ./output -a 0x12345678 --value 0xDEADBEEF
"""

import argparse
import ast
import inspect
import json
import os
import sys

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, currentdir + "/../../../tbottest")

from tbottest.tc.registermap import REGISTERMAP  # noqa: E402


def parse_arguments():
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze a register value for a specific SoC."
    )

    parser.add_argument(
        "-s", "--soc", required=True, help="Name of the SoC (example imx8mp)"
    )

    parser.add_argument(
        "-i",
        "--input-dir",
        default="scripts/registermap",
        help="Directory where the regsitermap json file is located",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        default="scripts/registermap",
        help="Directory where the result will be written",
    )

    parser.add_argument(
        "--regsfile",
        default=None,
        help="File with a list of registername, index, value lines",
    )

    # One positional argument for address-value pairs
    parser.add_argument(
        "regs",
        help=(
            "JSON-like list of register dictionaries, e.g. "
            '\'[{"address":"0x30330070","value":"0x00000000"}]\''
        ),
    )

    args = parser.parse_args()

    # Parse the positional argument as Python literal or JSON
    try:
        # Try Python literal (allows single quotes)
        args.regs = ast.literal_eval(args.regs)
    except Exception:
        try:
            args.regs = json.loads(args.regs)
        except Exception:
            print("Error: Invalid format for register list.")
            print('Expected: \'[{"address":"0xADDR","value":"0xVAL"}]\'')
            sys.exit(1)

    # Validate structure
    if not isinstance(args.regs, list) or not all(
        isinstance(r, dict) and "address" in r and "value" in r for r in args.regs
    ):
        print(
            "Error: The register list must be a list of objects with 'address' and 'value' keys."
        )
        sys.exit(1)

    return args


def analyze_register(args):
    """
    Analyze a given address and value using the SoC data.
    For now, this function just returns a mock result.
    """
    os.makedirs(args.input_dir, exist_ok=True)
    input_path = os.path.join(args.input_dir, f"{args.soc}_registers.json")
    regmap = REGISTERMAP(input_path)
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, f"{args.soc}_result.txt")
    if args.regsfile:
        registers = []
        with open(args.regsfile, "r") as f:
            for line in f:
                l = line.strip()
                name = l.split(" ")[0]
                index = l.split(" ")[1]
                value = l.split(" ")[2]
                try:
                    addr = regmap.registername_to_address(name, index)
                    #print(f'name {name} index {index} name {name} addr {addr} value {value}')
                    registers.append({"address":addr, "value":value})
                except:
                    print(f'register {name} not found!!')
                    pass
    else:
        registers = args.regs

    for regs in registers:
        regmap.registermap_dump_register_file(output_path, regs["address"], regs["value"])


def main():
    args = parse_arguments()

    analyze_register(args)


if __name__ == "__main__":
    main()
