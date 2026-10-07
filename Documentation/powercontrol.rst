.. py:module:: tbottest.powercontrol

``tbottest.powercontrol``
=============================
A module containing various additional connectors for controlling power.  These
are:

- :py:class:`~tbottest.powercontrol.GpiopmControl` - Power using a gpio pin
- :py:class:`~tbottest.powercontrol.PowerShellScriptControl` - Power using a shell script.
- :py:class:`~tbottest.powercontrol.ShellyControl` - Power using a Shelly device through `shelly-ctrl`_.
- :py:class:`~tbottest.powercontrol.SispmControl` - Power using `sispmctl`_.
- :py:class:`~tbottest.powercontrol.TboxCtrlControl` - Power using `tbox-ctrl`_.
- :py:class:`~tbottest.powercontrol.TinkerforgeControl` - Power using `tinkerforge`_.
- :py:class:`~tbottest.powercontrol.TM021Control` - Power using DH Electronic TM-021 4-fach Relaismodul `dh`_.

.. _shelly-ctrl: https://github.com/EmbLux-Kft/shelly-ctrl
.. _sispmctl: http://sispmctl.sourceforge.net/
.. _tinkerforge: https://www.tinkerforge.com/
.. _tbox-ctrl: https://gitlab.nabladev.com/nabla/tbox/tbox-ctrl
.. _dh: https://www.dh-electronics.com/

.. autoclass:: tbottest.powercontrol.GpiopmControl
   :members: gpiopmctl_pin, gpiopmctl_state

.. autoclass:: tbottest.powercontrol.PowerShellScriptControl
   :members: shell_script

.. autoclass:: tbottest.powercontrol.ShellyControl
   :members: shelly_device, shelly_id, shelly_command, shelly_tooldir, shelly_repo, shelly_install, shelly_timeout

.. autoclass:: tbottest.powercontrol.SispmControl
   :members: sispmctl_device, sispmctl_port

.. autoclass:: tbottest.powercontrol.TboxCtrlControl
   :members: tbox_powerpin, tbox_vid, tbox_pid

.. autoclass:: tbottest.powercontrol.TinkerforgeControl
   :members: channel, uid

.. autoclass:: tbottest.powercontrol.TM021Control
   :members: tm021_device, tm021_baudrate, tm021_timeout, tm021_address, tm021_port, tm021_debug
