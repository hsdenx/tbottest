#!/usr/bin/python3

import re
import sys
import getopt


def main(argv):
    inputfile = ""

    try:
        opts, args = getopt.getopt(argv, "hi:", ["ifile="])
    except getopt.GetoptError:
        print("check_cangen_output.py -i <inputfile>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            print("check_cangen_output.py -i <inputfile>")
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg

    file1 = open(inputfile, "r")
    Lines = file1.readlines()

    maxv = 0
    for line in Lines:
        # print("Line ", line.strip())
        # example line
        # T: 0 (  600) P:99 I:1000 C:      0 Min:1000000 Act:    0 Avg:    0 Max:       0
        try:
            found = re.search("Max:( *)(\d*)", line.strip()).group(2)  # noqa: W605
            val = int(found)
        except:  # noqa: E722
            found = None

        if found:
            if val > maxv:
                maxv = val

    print("Maximum ", maxv)


if __name__ == "__main__":
    main(sys.argv[1:])
