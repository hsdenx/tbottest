.. py:module:: tbottest.connector

``tbottest.connector``
==========================
A module containing various additional connectors:

- :py:class:`~tbottest.connector.KermitConnector` - Console on localhost using `kermit`_.
- :py:class:`~tbottest.connector.PicocomConnector` - Console on localhost using `picocom`_.

.. _kermit: http://www.kermitproject.org/
.. _picocom: https://github.com/npat-efault/picocom

.. autoclass:: tbottest.connector.KermitConnector
   :members: kermit_cfg_file

.. autoclass:: tbottest.connector.PicocomConnector
