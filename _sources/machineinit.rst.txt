.. py:module:: tbottest.machineinit

``tbottest.machineinit``
=============================
A module containing various additional machine initializers.  These
are:

- :py:class:`~tbottest.machineinit.UsbSdpLoad` - loading bootloader with `imx_usb_loader`_.
- :py:class:`~tbottest.machineinit.LauterbachLoad` - loading bootloader with `Lauterbach debugger trace32`_.
- :py:class:`~tbottest.machineinit.DFUUTIL` - loading bootloader with `dfuutil`_.
- :py:class:`~tbottest.machineinit.UUULoad` - loading bootloader with `uuu`_.

.. _dfuutil: https://dfu-util.sourceforge.net/
.. _imx_usb_loader: https://github.com/boundarydevices/imx_usb_loader
.. _uuu: https://github.com/NXPmicro/mfgtools

.. autoclass:: tbottest.machineinit.DFUUTIL
   :members: dfuutil_loader_steps, _init_machine

.. autoclass:: tbottest.machineinit.UsbSdpLoad
   :members: get_imx_usb_loader, usb_loader_bins

.. autoclass:: tbottest.machineinit.UUULoad
   :members: get_uuu_tool, uuu_loader_steps

.. autoclass:: tbottest.machineinit.LauterbachLoad
   :members: get_trace32_config, get_trace32_script
