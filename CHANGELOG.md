# Changelog

## [Unreleased]
### Added
- An entry of `lnx_commands` may leave out `"val"` and only run its
  command, and may have `"mode": "exec"`, then its return code does not
  matter, as for `linux_init` (`lnx_check_cmd()`). So commands that
  prepare the checks, such as stopping a service, fit in the same list.
- `board_lnx_cangen` sends with `cansequence` of canutils when the
  sending machine has no cangen, e.g. a board with canutils of
  Pengutronix, so the direction board2lab of `generic_lnx_test_cangen`
  works there. Its frames have the fixed CAN ID 2 and one data byte,
  counted up, and there is no gap; `check_cangen_log()` takes the CAN ID
  as `canid`.
- create_setup.sh writes a `.gitignore` into the setup directory if there
  is none, from the template `tbottest/tbotconfig/gitignore`. It keeps
  tbot/, tbottest/, log/, `*.pyc` and `*.swp` out of a git repository of
  the setup.
- An entry of `ub_env` or of a group `ub_env_<name>` may have `"append"`
  or `"remove"` instead of `"val"`, words added to or taken out of the
  value the U-Boot variable has on the board (`ub_env_apply()`,
  `ub_env_edit()`). Together with `"flag"`, several flags can each add a
  word to the same variable, e.g. to `optargs`, what needed
  `set_ub_board_specific()` in boardspecific.py before.
- Unit tests for the generic testcases of `tc/generic_board.py`, for the
  configuration a testcase reads, the calls it makes with it, the skip
  without its key and the counts of `generic_lnx_all`. The kas testcases
  are not covered yet.
- `generic_lnx_test_cangen`, run by `generic_lnx_all`, runs
  `board_lnx_cangen` for every entry of the board configuration key
  `cangen`, from the lab host to the board and from the board to the lab
  host (`cangen_config_calls()`). An entry names the CAN interfaces of
  board and lab host (`boarddev`, `labdev`) and may restrict the
  `directions`.
- `generic_lnx_test_rs485`, run by `generic_lnx_all`, runs
  `board_lnx_rs485` once for every entry of the board configuration key
  `rs485`, whose keys are its parameters (`rs485_config_kwargs()`).
- `linux_safe_init_prompt` in the board configuration, True by default,
  sets tbot's `safe_init_prompt`, so the prompt is read with
  `read_until_prompt_safe()` while tbot sets up the linux shell.
- Section `TC_BOARDNAME.TESTCASENAME` of the board configuration. While a
  testcase decorated with `tc_config()` or `require_cfg()` runs, a key is
  searched there first, then in `TC_BOARDNAME` and `TC`. There is
  deliberately no section `TC_TESTCASENAME` for all boards.
- `get_config_literal()` reads a key as Python literal.
- Configuration as JSON. `tbot.json` and `BOARDNAME.json` replace
  `tbot.ini`, `BOARDNAME.ini` and `boardspecific.py` when the flags
  `inifile:` and `boardfile:` name `.json` files. Values that depend on a
  run are expressions (`${env:NAME}`, `${flag:NAME}`, `${lab:key}`,
  `${tbot:SECTION:key}`), which also work in ini files. An `ub_env` entry
  with `"flag"` is set only with that flag. `generic_config_to_json` writes
  a configuration as JSON, `create_setup.sh --json` sets one up.
- Groups of the U-Boot environment (`ub_env_<group>`), selected with the
  flag `ub_env:` or by the boot command.
- `cmd_versions` presets `cmd_get_version()` of tbot for the lab host, the
  build hosts and the board. The testcase `generic_cmd_versions` finds the
  versions out and installs missing packages with `cmd_versions_install`.
- `testdir`, a directory for testcases on the build host, the lab host and
  the board.
- Power control with a shell script, a GPIO, Tinkerforge, a Shelly device
  (`ShellyControl`), a tbox SYSTEM Controller Modul (`TboxCtrlControl`), a
  tbox lab host through hwdamon-dut-power (`TboxHwdaemonControl`) and the
  DH electronics TM-021 relay module. Console and power connector are
  detected from the configuration.
- Console access with a script of your own (`ScriptConnector`) and with
  telnet (`TelnetConnector`). Picocom sends slowly with `slow_send_delay`
  and `slow_send_chunksize`, the kermit options are configurable.
- Loading after power on with dfu-util and over the serial line (sb), and
  the Abatron BDI2000, which runs `poweron_cmds` after power on and
  selects its configuration file with `configname:`. `tc/bdi2000.py` opens
  a telnet session to the BDI2000.
- More than one lab host (`LABHOST_<name>`, flag `labname:`), password
  login and a configurable ssh authenticator, board locking, the boot mode
  switched with sd-mux or a shell command, and a local build host (flag
  `buildername:local`). The lab init runs once per boot of the lab host,
  the ethernet setup once per board.
- U-Boot without return codes (`uboot_has_retcode`), boards that log in
  automatically, `linux_plain_prompt`, and `linux_netcmd` to choose `ip` or
  `ifconfig`.
- Testcases for process measurement with top and ps (with gnuplot), register
  dumps with register maps of NXP i.MX and STM32MP157 (and the standalone
  `regdump` tool), the generic linux tests with `generic_lnx_all`, iperf
  and ping, the unit tests of U-Boot, U-Boot builds with buildman, a boot
  counter, swupdate over the embedded web server, the watchdog,
  `lnx_mtd_dump` and the hello world build of a Yocto SDK.
  `exec_check()` and `exec0_check()` abort early on death strings.
- kas with an interactive shell, `--runtime-args`, `.netrc`, `auto.conf`,
  bitbake targets, `kas_build_dir`, `kas_mounts`, a configurable deploy path
  and the flag `kaskeepconfig`.
- `create_setup.sh` asks for console and power control with `--inter`,
  writes a `setup.sh` with aliases, copies the CI testcases only with
  `--ci`, checks out tbottest with `-b` or `-c`, takes tbot from the branch
  `v0.10.10-emb` of github.com/EmbLux-Kft/tbot and updates existing clones.
  `completions.sh` completes the testcases and the aliases.
- `newtbot_starter.py` takes the paths from `TBOTCONFIGPATH` and
  `TBOTTESTPATH` and sets `TBOT_STARTTIME` for the argument files.
  `generators/console.py` shows a JSON log as tbot showed it on the console.
- Documentation of every tbot flag, the Tips section, testcase parameters,
  the generic testcases and how to start them, and the pages CHANGELOG,
  CONTRIBUTING and LICENSE.
- A pytest unit test suite with its own CI workflow, and `pyproject.toml`.

### Changed
- `check_yocto_build_install_sdk()` starts the SDK installer as
  linux.Path instead of a path built as string.
- `lnx_create_random()` takes a linux.Path as well as a string, and the
  RS485 test passes its paths as linux.Path instead of `_local_str()`.
- `lnx_can_write_dump_compare()` has no parameters `lab` and `lnx` any
  more. `lab` only decided whether to use sudo, `lnx` was not used.
- `board_setup_can()` runs `ip` with `lnx_sudo()`, so with sudo unless
  the machine is logged in as root. Its parameter `usesudo` and
  `sudo_exec0()` of `tc/can.py` are gone, and `lnx_can_write_dump_compare()`
  no longer guesses from `lab == lnxsend` whether sudo is needed.
- `board_lnx_cangen` checks the candump log itself, with the new
  `check_cangen_log()`, on the output of `cat` on the board. Nothing is
  copied to the lab host any more, so the parameters `lab` and
  `labtbottestcasepath` and `tc/files/check_cangen_output.py` are gone.
  It checks the number of frames, interface, CAN ID, data length and
  data, reports every difference and raises instead of stopping in an
  interactive shell. The transfer rate comes from the candump timestamps.
- The generic testcases read their keys when they run, with the
  `get_config*()` methods of `cfggeneric`, so they find their own section.
  `require_cfg()` takes the name of the key. `cfggeneric.kas_config(lab, bh)`
  and `cfggeneric.get_lnx_dump_files()` replace `cfg.kas` and
  `cfg.lnx_dump_files`.
- tbot is v0.10.10.
- `tbot.ini` and the board configuration are read through the helpers of
  `tbottest.initconfig`, the board name comes from the flag `boardname:`,
  and `boardspecific.py` sits next to `tbot.ini`.
- Configuration values are read with `ast.literal_eval()` instead of
  `eval()`.
- Commands that need root rights run without sudo when tbot is logged in
  as root.
- `GenericUBoot.exec()` reads back the echo of the command line like tbot.

### Fixed
- Command line completion of tbottest testcases, e.g.
  `$tbtc.generic_board.gen<TAB>`, found nothing, because tbot looks a
  module up below the working directory, and in a setup made by
  create_setup.sh the package is tbottest/tbottest there. `newtbot_completion.py`, which
  `newtbot_starter.py` installs into tbot, looks it up through sys.path
  as an import does. `completions.sh` completes a variable name such as
  `$tbtc` without the space bash-completion adds, so the module path can
  follow.
- `board_lnx_cangen` hung after cangen on a board with candump of
  canutils (Pengutronix), which ends on SIGTERM only when the next frame
  arrives; `stop_candump()` kills it after 2 seconds. Such a candump has
  no `-L` either: tbot's `cmd_get_version()` reports it as `canutils`
  (`candump_is_canutils()`), and its log is checked without interface
  and without transfer rate, it has no timestamps. A sender without
  cangen (canutils has none) stops with an error naming the machine.
  candump and cangen are in `TBOTTEST_COMMANDS` now, with the Debian
  package can-utils for `cmd_versions_install`.
- The check of `board_lnx_cangen` did not let the data counter wrap, so
  it failed after 256 frames with `dllength=1`; it compared the log with
  the board path on the lab host and copied it from a fixed IP address.
- The default `testdir` of the lab host and of `[SSHMACHINE]`,
  `<workdir>/tbottests`, got a double slash when `workdir` ended in one.
- A relative `workdir` or `testdir` of a build host reached over ssh was
  taken from the directory tbot runs in on the local machine. It is taken
  from the home directory of the build host now; `[BUILDHOST_local]` keeps
  the directory tbot runs in, where its shell starts.
- `KAS.kas_copy()` was annotated with the module `tbot.machine.linux.path`
  instead of `linux.Path`, so the documentation showed the module.
- A race in `lab_get_lock()` of the board locking.
- Unescaped values in shell command strings of testcases.
- Retry loops in `board_wait_for_device()`, `lnx_wait_for_ip()` and the
  check of `tbot_start_thread()`.
- `ps_parse_top()` dropped the last loop, the IPv6 regex of
  `_lnx_get_ipaddr()` did not match, `TM021Control.poweroff()` and the CAN
  testcases failed with an AttributeError.
- Copies of the ini files were left behind.

### Removed
- The bootlin and linaro toolchains of the lab host. The classes are gone
  from tbot, the lab host raises like the build hosts do.
- The attributes of `GenericBoardConfig` for the keys of the board
  configuration (`cfg.dmesg`, `cfg.kas`, ...). It keeps what belongs to the
  board (`tmpdir`, `shelltype`, ...).
- `setup.py`, `pyproject.toml` replaces it.
- `tftp_subdir` in the board configuration, `tftpsubdir` of the lab section
  replaces it.
