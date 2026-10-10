Contributing to tbot-test
=========================

Hello there!  Thank you for taking your time to help *tbottest* become a better
piece of software!  To make this go as smoothly as possible, please follow the
guidelines below:

## Commit Style
### `pre-commit`
When sending a pull-request or patch, please make sure to use the supplied
[pre-commit](https://pre-commit.com/) config.  To do so, install the tool and
run `pre-commit install` inside the repository.  Now, if you `git commit`,
*pre-commit* will run a bunch of tests to ensure your changes don't break
anything else!

### Commit Messages
Your commit messages should look like this:
`<relevant part>: Message in imperative style (present tense)`

If your changes apply to tbottest as a whole, you can leave out the `<module>:`.
Examples:

```text
board.uboot: Fix bootlog missing if not autobooting
doc: Add flags documentation
loader: Show traceback of errrors
Fix a few spelling mistakes
```

### Licensing
Always add a signoff-line to your commits.  By doing so, you certify the
"Developer Certificate of Origin" which can be found at the end of this
document.


## Coding Style
### Formatting
Formatting convention is [black](https://github.com/ambv/black), this is also
enforced by the *pre-commit* config.  Just write code however you want and let
*black* format it for you ;)

### Imports
Please don't import things into your namespace that you don't explicitly want
to have available for downstream users.  Prefer importing the module to keep
your namespace clean and to give readers the ability to easily see where some
object was pulled in from.

**Good**:

```python
from tbot.machine import channel

# Later on
def foo() -> channel.Channel:
    ...
```

**Bad**:

```python
from tbot.machine.channel import Channel

# Now Channel is polluting our namespace :(
def foo() -> Channel:
    ...
```

There might be some exceptions where the latter is definitely perferable, but
in most cases it isn't.

## Developer Certificate of Origin
```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```
