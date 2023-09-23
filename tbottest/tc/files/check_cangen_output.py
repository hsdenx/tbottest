import re
import sys
import getopt


def hexStrEndianSwap(theString):
    """Rearranges character-couples in a little endian hex string to
    convert it into a big endian hex string and vice-versa. i.e. 'A3F2'
    is converted to 'F2A3'

    @param theString: The string to swap character-couples in
    @return: A hex string with swapped character-couples. -1 on error."""

    # We can't swap character couples in a string that has an odd number
    # of characters.
    if len(theString) % 2 != 0:
        return -1

    # Swap the couples
    swapList = []
    for i in range(0, len(theString), 2):
        swapList.insert(0, theString[i : i + 2])

    # Combine everything into one string. Don't use a delimeter.
    return "".join(swapList)


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

    canidlast = 0
    candatalast = 0

    # Strips the newline character
    for line in Lines:
        # (1598423840.039597) can0 08C#8C00000000000000
        match = re.match(
            r"\((?P<time>\d+.\d+)\) (?P<candev>\w+\d+) (?P<canid>\w+)#(?P<candata>\w+)",
            line,
        )
        assert match is not None, f"Failed to parse line ({line!r})!"

        canid = match.group("canid")

        ci = int(canid, base=16)
        if ci != canidlast:
            raise RuntimeError(f"diff in line {line} canid: {ci} should be {canidlast}")
        else:
            canidlast = ci + 1
            if canidlast == 2048:
                canidlast = 0

        candata = match.group("candata")
        cdi = int(hexStrEndianSwap(candata), base=16)
        if cdi != candatalast:
            raise RuntimeError(
                f"diff in line {line} candata: {cdi} should be {candatalast}"
            )
        else:
            candatalast = cdi + 1


if __name__ == "__main__":
    main(sys.argv[1:])
