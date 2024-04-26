.. py:module:: tbottest.common.boardlocking

``tbottest.boardlocking``
=========================

It is possible to lock a board in a lab, so only tbot
calls with a valid ``lockid`` are started. A ``lockid``
is a simple string, passed to tbot with the tbot flag


.. code-block:: ini

   lablockid:<your locking ID>

Enable this feature in ``tbot.ini`` file with

.. code-block:: ini

   [LABHOST]
   uselocking = yes

default is ``no``, so disabled.


Example run
-----------

reserve a board on the lab host
...............................

reserve a board on a lab host with lockid ``foobar``

.. code-block:: bash

    $ tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar tbotconfig.interactive.lab

Now tbot created on your lab host the following lockfile ``lab.tmpdir/boardname-lablock``
which contains the lockid string.

You can only access the board now with passing ``-f lablockid:foobar``, all
other tbot calls will fail!

start a tbot call with the wrong tbot flag

.. code-block:: bash

   $ tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foo tbotconfig.interactive.lab
        tbot starting ...
        ├─TBOT.FLAGS ['boardfile:tbotconfig/foo/foo.ini', 'do_power', 'inifile:tbotconfig/foo/tbot.ini', 'lablockid:foo', 'noboardethinit', 'noethinit', 'picocom', 'useifconfig']
        ├─boardname now foo
        [...]
        ├─Calling lab ...
        [...]
        │   │   ├─passed lockid foo is not the same as lockid in file /tmp/tbot/pi/foo/foo-lablock. Boardname foo is locked through ID foobar
        │   │   └─Fail. (0.493s)
        [...]
        ├─────────────────────────────────────────
        └─FAILURE (3.484s)

call tbot without lockid fails too:

.. code-block:: bash

        $ tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth tbotconfig.interactive.lab
        tbot starting ...
        ├─TBOT.FLAGS ['boardfile:tbotconfig/foo/foo.ini', 'do_power', 'inifile:tbotconfig/foo/tbot.ini', 'noboardethinit', 'noethinit', 'picocom', 'useifconfig']
        ├─boardname now foo
        [...]
        ├─Calling lab ...
        [...]
        │   ├─Calling lab_get_lock ...
        [...]
        │   │   │   └─Done. (0.107s)
        │   │   └─Fail. (0.496s)
        │   └─Fail. (3.154s)
        ├─Exception:
        │   Traceback (most recent call last):
        [...]
        │   RuntimeError: NO LABLOCKID passed, please pass tbot flag 'lablockid:<yourlockid>'
        ├─────────────────────────────────────────
        └─FAILURE (3.329s)



remove the reservation
......................

delete the lock with

.. code-block:: bash

   $ tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar tbottest.common.boardlocking.lab_rm_lock
        tbot starting ...
        ├─TBOT.FLAGS ['boardfile:tbotconfig/foo/foo.ini', 'do_power', 'inifile:tbotconfig/foo/tbot.ini', 'lablockid:foobar', 'noboardethinit', 'noethinit', 'picocom', 'useifconfig']
        ├─boardname now foo
        [...]
        ├─Calling lab_rm_lock ...
        [...]
        │   ├─[lab8] rm /tmp/tbot/pi/foo/foo-lablock
        │   └─Done. (5.862s)
        ├─────────────────────────────────────────
        └─SUCCESS (5.916s)


Functions
---------

.. automodule:: tbottest.common.boardlocking
   :members:
