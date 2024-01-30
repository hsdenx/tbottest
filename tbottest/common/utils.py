import re


def string_to_dict(string: str, pattern: str) -> dict:
    """
    convert a string into a dictionary via a pattern

    example pattern:
    'hello, my name is {name} and I am a {age} year old {what}'

    string:
    'hello, my name is dan and I am a 33 year old developer'

    returned dict:
    {'age': '33', 'name': 'dan', 'what': 'developer'}
    from:
    https://stackoverflow.com/questions/11844986/convert-or-unformat-a-string-to-variables-like-format-but-in-reverse-in-p
    """
    # do not allow spaces in key names!
    regex = re.sub(r'{(.+?)}', r'(?P<_\1>[^\\s]+)', pattern)
    match = re.search(regex, string)
    assert match is not None, f"The pattern {regex!r} was not found!"
    values = list(match.groups())
    keys = re.findall(r"{(.+?)}", pattern)
    _dict = dict(zip(keys, values))
    return _dict
