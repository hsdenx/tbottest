"""
Unit tests for tbottest/common/boardlocking.py: lab_get_lock's atomic
lock creation (the TOCTOU fix) and the errstr-typo fixes in
lab_get_lock/lab_rm_lock.

Since there is no real lab host here, FakeLab below simulates just
enough of a remote filesystem (a plain dict) for lab_get_lockname's
path arithmetic, is_file() checks, and the "sh -c 'set -C; ...'"
atomic-create call used by lab_get_lock to behave like the real
thing: creating a file only succeeds if it didn't already exist.
"""

import os
import sys

import pytest

from conftest import install_fake_initconfig, load_module

install_fake_initconfig(boardname="testboard")

boardlocking = load_module(
    "tbottest_common_boardlocking",
    os.path.join(
        os.path.dirname(__file__), "..", "tbottest", "common", "boardlocking.py"
    ),
)

tbot = sys.modules["tbot"]


class FakeFS:
    def __init__(self):
        self.files = {}


class FakeLockPath(str):
    fs = None

    def __truediv__(self, other):
        p = FakeLockPath(f"{self}/{other}")
        p.fs = self.fs
        return p

    def _local_str(self):
        return str(self)

    def is_file(self):
        return str(self) in self.fs.files


class FakeLab:
    def __init__(self):
        self.fs = FakeFS()

    def tmpdir(self):
        p = FakeLockPath("/lab/tmp")
        p.fs = self.fs
        return p

    def exec0(self, *args):
        ret, out = self.exec(*args)
        if ret != 0:
            raise RuntimeError(f"exec0 failed: {args}")
        return out

    def exec(self, *args):
        if args[0] == "sh" and args[1] == "-c":
            # set -C; echo "$1" > "$2"  -- $0=args[3] $1=args[4] $2=args[5]
            lockid, path = args[4], str(args[5])
            if path in self.fs.files:
                return (1, "")
            self.fs.files[path] = str(lockid) + "\n"
            return (0, "")
        if args[0] == "cat":
            path = str(args[1])
            return (0, self.fs.files.get(path, ""))
        if args[0] == "rm":
            path = str(args[1])
            self.fs.files.pop(path, None)
            return (0, "")
        raise AssertionError(f"unexpected exec: {args}")


class TestLabGetLock:
    def test_no_lablockid_flag_raises(self):
        lab = FakeLab()
        with pytest.raises(RuntimeError, match="NO LABLOCKID passed"):
            boardlocking.lab_get_lock(lab)

    def test_acquires_free_lock(self):
        lab = FakeLab()
        tbot.flags.add("lablockid:mysession")
        ret = boardlocking.lab_get_lock(lab)
        assert ret == (0, "mysession")
        ret2, lockid = boardlocking.lab_get_lock_info(lab)
        assert (ret2, lockid) == (0, "mysession")

    def test_atomic_create_fails_if_already_locked_by_someone_else(self):
        """
        This is the TOCTOU-fix regression test: simulate two
        "concurrent" callers racing for the same lock. Only the first
        atomic create may succeed; the second must see the lock as
        already held (not silently also succeed).
        """
        lab = FakeLab()
        tbot.flags.add("lablockid:first")
        boardlocking.lab_get_lock(lab)

        tbot.flags.clear()
        tbot.flags.add("lablockid:second")
        with pytest.raises(RuntimeError, match="passed lockid second is not the same"):
            boardlocking.lab_get_lock(lab)

        # the lock must still show the *first* session's id, unchanged
        assert boardlocking.lab_get_lock_info(lab) == (0, "first")

    def test_reacquire_with_same_lockid_does_not_raise(self):
        lab = FakeLab()
        tbot.flags.add("lablockid:mysession")
        boardlocking.lab_get_lock(lab)
        # calling again with the identical lockid must not raise
        boardlocking.lab_get_lock(lab)

    def test_error_message_contains_real_details_not_the_string_errstr(self):
        """Regression test for the raise RuntimeError("errstr") typo:
        the literal string "errstr" must never be the exception text."""
        lab = FakeLab()
        tbot.flags.add("lablockid:first")
        boardlocking.lab_get_lock(lab)

        tbot.flags.clear()
        tbot.flags.add("lablockid:second")
        with pytest.raises(RuntimeError) as exc_info:
            boardlocking.lab_get_lock(lab)
        assert str(exc_info.value) != "errstr"
        assert "second" in str(exc_info.value)
        assert "first" in str(exc_info.value)


class TestLabRmLock:
    def test_no_lablockid_flag_raises(self):
        lab = FakeLab()
        with pytest.raises(RuntimeError, match="NO LABLOCKID passed"):
            boardlocking.lab_rm_lock(lab)

    def test_wrong_lockid_raises_with_real_message(self):
        lab = FakeLab()
        tbot.flags.add("lablockid:first")
        boardlocking.lab_get_lock(lab)

        tbot.flags.clear()
        tbot.flags.add("lablockid:wrong")
        with pytest.raises(RuntimeError) as exc_info:
            boardlocking.lab_rm_lock(lab)
        assert str(exc_info.value) != "errstr"
        assert "wrong" in str(exc_info.value)

    def test_correct_lockid_removes_lock(self):
        lab = FakeLab()
        tbot.flags.add("lablockid:mysession")
        boardlocking.lab_get_lock(lab)
        assert boardlocking.lab_get_lock_info(lab)[0] == 0

        boardlocking.lab_rm_lock(lab)
        assert boardlocking.lab_get_lock_info(lab)[0] == 1
