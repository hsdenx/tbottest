# Changelog

## [Unreleased]
### Added
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
  and the pages CHANGELOG, CONTRIBUTING and LICENSE.
- A pytest unit test suite with its own CI workflow, and `pyproject.toml`.

### Changed
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
- A race in `lab_get_lock()` of the board locking.
- Unescaped values in shell command strings of testcases.
- Retry loops in `board_wait_for_device()`, `lnx_wait_for_ip()` and the
  check of `tbot_start_thread()`.
- `ps_parse_top()` dropped the last loop, the IPv6 regex of
  `_lnx_get_ipaddr()` did not match, `TM021Control.poweroff()` and the CAN
  testcases failed with an AttributeError.
- Copies of the ini files were left behind.

### Removed
- `setup.py`, `pyproject.toml` replaces it.
- `tftp_subdir` in the board configuration, `tftpsubdir` of the lab section
  replaces it.
