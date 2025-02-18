.. py:module:: tbottest.powercontrol

``tbottest.powercontrol``
=============================
A module containing various additional connectors for controlling power.  These
are:

- :py:class:`~tbottest.powercontrol.GpiopmControl` - Power using a gpio pin
- :py:class:`~tbottest.powercontrol.PowerShellScriptControl` - Power using a shell script.
- :py:class:`~tbottest.powercontrol.SispmControl` - Power using `sispmctl`_.
- :py:class:`~tbottest.powercontrol.TinkerforgeControl` - Power using `tinkerforge`_.

.. _sispmctl: http://sispmctl.sourceforge.net/
.. _tinkerforge: https://www.tinkerforge.com/

.. autoclass:: tbottest.powercontrol.GpiopmControl
   :members: gpiopmctl_pin, gpiopmctl_state

.. autoclass:: tbottest.powercontrol.PowerShellScriptControl
   :members: shell_script

.. autoclass:: tbottest.powercontrol.SispmControl
   :members: sispmctl_device, sispmctl_port

.. autoclass:: tbottest.powercontrol.TinkerforgeControl
   :members: channel, uid
