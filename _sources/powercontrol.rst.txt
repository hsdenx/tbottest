.. py:module:: tbottest.powercontrol

``tbottest.powercontrol``
=============================
A module containing various additional connectors for controlling power.  These
are:

- :py:class:`~tbottest.powercontrol.SispmControl` - Power using `sispmctl`_.
- :py:class:`~tbottest.powercontrol.TinkerforgeControl` - Power using `tinkerforge`_.

.. _sispmctl: http://sispmctl.sourceforge.net/
.. _tinkerforge: https://www.tinkerforge.com/

.. autoclass:: tbottest.powercontrol.SispmControl
   :members: sispmctl_device, sispmctl_port

.. autoclass:: tbottest.powercontrol.TinkerforgeControl
   :members: channel, uid
