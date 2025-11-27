def get_bit_range(hex_str: str, bit_range: str, lsb_first: bool = False) -> str:
    """
    extract bits defined in 0 based range from a hexstring
    """
    value = int(hex_str, 16)

    bit_range = bit_range.strip()

    # parse range
    if "-" in bit_range:
        parts = bit_range.split("-")
        if len(parts) != 2:
            raise ValueError(f"invalid range: {bit_range}")
        start_bit, end_bit = map(int, parts)
    elif ":" in bit_range:
        parts = bit_range.split(":")
        if len(parts) != 2:
            raise ValueError(f"invalid range: {bit_range}")
        start_bit, end_bit = map(int, parts)
    else:
        start_bit = end_bit = int(bit_range)

    if start_bit < 0 or end_bit < 0:
        raise ValueError("bitpositions start from 0.")

    start = min(start_bit, end_bit)
    end = max(start_bit, end_bit)

    bit_length = end - start + 1
    mask = (1 << bit_length) - 1
    bits_value = (value >> start) & mask

    bits_str = format(bits_value, f"0{bit_length}b")
    if lsb_first:
        bits_str = bits_str[::-1]

    return bits_str
