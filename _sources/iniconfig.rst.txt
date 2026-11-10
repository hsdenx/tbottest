.. py:module:: tbottest.initconfig.py

``tbottest.initconfig``
=======================

.. _iniconfighelperfunctions:

helper functions
----------------

Values of the lab and the board configuration (ini or JSON) are read through these
functions, or the methods of :py:class:`~tbottest.initconfig.IniTBotConfig`
and :py:class:`~tbottest.initconfig.IniConfig` built on them, never through
``config_parser`` directly. Then the order of the sections (``TC_BOARDNAME``
before ``TC``, ``LABHOST_<labname>`` for the lab host) is known in one place.

.. autofunction:: tbottest.initconfig.init_get_config

.. autofunction:: tbottest.initconfig.init_config_sections

.. autofunction:: tbottest.initconfig.init_testcase

.. autofunction:: tbottest.initconfig.init_current_testcase

.. autofunction:: tbottest.initconfig.init_get_config_int

.. autofunction:: tbottest.initconfig.init_get_config_literal

.. autofunction:: tbottest.initconfig.init_get_config_bool

.. autofunction:: tbottest.initconfig.init_get_config_keys

.. autofunction:: tbottest.initconfig.init_lab_get_config

.. autofunction:: tbottest.initconfig.init_section_get_config

.. autofunction:: tbottest.initconfig.init_section_get_config_bool

.. autofunction:: tbottest.initconfig.init_config_to_bool

.. autofunction:: tbottest.initconfig.init_has_section

.. autofunction:: tbottest.initconfig.init_find_sections

.. autofunction:: tbottest.initconfig.init_read_inifile

.. autofunction:: tbottest.initconfig.init_read_jsonfile

.. autofunction:: tbottest.initconfig.init_read_configfile

.. autofunction:: tbottest.initconfig.init_config_substitute

.. autofunction:: tbottest.initconfig.init_substitute_configparser

.. autofunction:: tbottest.initconfig.init_json_value_to_str

.. autofunction:: tbottest.initconfig.init_config_to_json_dict

.. autofunction:: tbottest.initconfig.generic_get_boardname

.. autofunction:: tbottest.initconfig.copy_file

.. autofunction:: tbottest.initconfig.replace_in_file

.. autofunction:: tbottest.initconfig.find_in_file_and_append

.. autofunction:: tbottest.initconfig.find_in_file_and_delete

classes
-------

- :py:class:`~tbottest.initconfig.IniTBotConfig` - Init generic setup from tbot.ini.

.. autoclass:: tbottest.initconfig.IniTBotConfig
   :members:

- :py:class:`~tbottest.initconfig.IniConfig` - Init generic setup from BOARDNAME.ini.

.. autoclass:: tbottest.initconfig.IniConfig
   :members:
