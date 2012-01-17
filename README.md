Abiquo API Jython client
========================

This project is a Jython client for the Abiquo Cloud Platform API, using
Jython as a wrapper to the [Official Java client](https://github.com/abiquo/jclouds-abiquo).
To understand the code and adapt it to your needs, you may want to take a
look at the official Java client project page:

 * [jclouds-abiquo Source code](https://github.com/abiquo/jclouds-abiquo)
 * [jclouds-abiquo Documentation](https://github.com/abiquo/jclouds-abiquo/wiki)

You can also find some usage examples in the [Project Wiki](https://github.com/nacx/kahuna/wiki).


Prerequisites
-------------

To run the examples you will need to install *Maven >= 2.2.1*, *JRE >= 1.6*
and ***Jython >= 2.5.2***.


Configuration
-------------

Since this project is currently in development process and we don't have any egg 
package ready, the *$JYHTONPATH* environment variable needs to be set manually:

    export JYTHONPATH=$(YOUR_PROJECT_HOME_DIRECTORY)
    
You can customize the data being generated by editing the **kahuna/constants.py** file.


Building
---------

You can run the provided Jython scripts using the provided wrapper, as shown in the
following examples. The wrapper example will build the classpath (if missing) with
all needed dependencies and export it as an environment to make it accessible to the
Jython scripts.

    sh wrapper.sh <address> env.py         # Create a default environment in the given hsot
    sh wrapper.sh <address> env.py clean   # Cleanup all data on the given host

Use it interactively
--------------------

You can also perform actions against the Api in an interactive way. You just need to
open a Jython shell from anywhere and load the context. The following example shows
how to edit a virtual datacenter interactively:

    nacx@laptop:~ $ sh wrapper.sh 10.60.1.222
    Jython 2.5.2 (Release_2_5_2:7206, Mar 2 2011, 23:12:06) 
    [Java HotSpot(TM) Server VM (Sun Microsystems Inc.)] on java1.6.0_18
    Type "help", "copyright", "credits" or "license" for more information.
    >>> from kahuna.session import ContextLoader
    >>> ctx = ContextLoader().load_context()
    Using endpoint: http://10.60.1.222/api
    >>> cloud = ctx.getCloudService()         
    >>> cloud.listVirtualDatacenters()
    [VirtualDatacenter [id=11, type=XENSERVER, name=Kaahumanu]]
    >>> vdc = cloud.listVirtualDatacenters()[0]
    >>> vdc.setName("Updated VDC")
    >>> vdc.update()
    >>> cloud.listVirtualDatacenters()         
    [VirtualDatacenter [id=11, type=XENSERVER, name=Updated VDC]]
    >>> ctx.close()
    >>> exit()


Note on patches/pull requests
-----------------------------
 
 * Fork the project.
 * Create a topic branch for your feature or bug fix.
 * Develop in the just created feature/bug branch.
 * Add tests for it. This is important so I don't break it in a future version unintentionally.
 * Commit.
 * Send me a pull request.


Issue Tracking
--------------

If you find any issue, please submit it to the [Bug tracking system](https://github.com/nacx/kahuna/issues) and we
will do our best to fix it.

License
-------

This sowftare is licensed under the MIT license. See LICENSE file for details.

