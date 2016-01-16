=====
Finja
=====

WARNING: This is a very nice hack, but it is still a hack.

Index and find your stuff:

.. code:: bash

   finja --index

Indexes the current directly.

.. code:: bash

   finja huhu

Find huhu in the index.

.. code:: bash

   finja -u huhu

Update outdated files and find huhu in the index.

.. code:: bash

   finja --index
   cd submdir
   find huhu

Thats it and it works.

Tipp: If you are sure that your system survives till everything is indexed use:

.. code:: bash

   eatmydata finja -i

By dv@winged.ch and ganwell@fangorn.ch
