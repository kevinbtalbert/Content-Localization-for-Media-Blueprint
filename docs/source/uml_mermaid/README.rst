Mermaid Diagram Catalog
=======================

This directory contains Mermaid diagram sources used by the
docs and README.

Rendering all diagrams
----------------------

Use the helper scripts in this folder to render all ``.mmd``
files at once.

.. code-block:: bash

   ./docs/source/uml_mermaid/render_all_diagrams.sh

By default, output is written to
``docs/source/uml_mermaid/rendered/`` as SVGs.

Optional flags:

.. code-block:: bash

   ./docs/source/uml_mermaid/render_all_diagrams.sh \
       --format png --renderer auto

Renderer modes are local-only:

- ``local``: requires ``mmdc`` on your ``PATH``
- ``docker``: uses Docker image ``minlag/mermaid-cli:latest``
- ``auto``: try ``local`` first, then ``docker``

Embedded in docs pages as inline mermaid blocks
-----------------------------------------------

- ``architecture_diagram.mmd`` -> ``index.rst``,
  ``architecture.rst``
- ``system_architecture.mmd`` -> ``overview.rst``
- ``push_mode_architecture.mmd`` -> ``architecture.rst``
- ``push_mode_data_flow.mmd`` -> ``architecture.rst``,
  ``overview.rst``
- ``push_mode_sequence.mmd`` -> ``architecture.rst``
- ``push_mode_threads.mmd`` -> ``architecture.rst``
- ``client_service_flow.mmd`` -> ``client_types.rst``
- ``client_architecture.mmd`` -> ``client_types.rst``
- ``direct_client_architecture.mmd`` -> ``client_types.rst``
- ``s2s_client_architecture.mmd`` -> ``client_types.rst``
- ``asd_client_architecture.mmd`` -> ``client_types.rst``
- ``lipsync_client_architecture.mmd`` -> ``client_types.rst``
- ``ui_demo_app_architecture.mmd`` -> ``demo_app.rst``

Converted and stored only
-------------------------

- ``controller_service_sequence.mmd``
- ``ui_demo_app_workflow.mmd``
- ``user_setup_workflow.mmd``
