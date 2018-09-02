```
 malcolm  ⎇  feature-gst-test-and-pocketsphinx  ⓔ 2.4.3  ~/dev/bossjones/pocketsphinx-build   pkg-config --variable prefix gstreamer-1.0
/usr/local/Cellar/gstreamer/1.14.1
 malcolm  ⎇  feature-gst-test-and-pocketsphinx  ⓔ 2.4.3  ~/dev/bossjones/pocketsphinx-build
```

# Get value of GST_PLUGIN_PATH
```
 malcolm  ⎇  feature-gst-test-and-pocketsphinx ?:1  ⓔ 2.4.3  ~/dev/bossjones/pocketsphinx-build  1   pkg-config --variable pluginsdir gstreamer-1.0
/usr/local/Cellar/gstreamer/1.14.1/lib/gstreamer-1.0
 malcolm  ⎇  feature-gst-test-and-pocketsphinx ?:1  ⓔ 2.4.3  ~/dev/bossjones/pocketsphinx-build
```

# SOURCE: https://cmusphinx.github.io/wiki/gstreamer/
```
In particular, pocketsphinx requires that the following three .pc files be available in order to configure the platform to build the GStreamer plugin :

gstreamer-1.0.pc
gstreamer-base-1.0.pc
gstreamer-plugins-base-1.0.pc
These files can be stored in different locations based on O/S preferences. For example, in Debian [Jessie], the first two are provided in the libgstreamer1.0-dev package and the last one is provided in the libgstreamer-plugins-base1.0-dev package. You can check that GStreamer is properly installed with

pkg-config --modversion gstreamer-plugins-base-1.0
You also should see the following line in configuration script output:

checking for GStreamer... yes
After installation you should make sure that GStreamer is able to find the pocketsphinx plugin. If you have installed pocketsphinx in /usr/local, then you may have to set the following environment variable:

export GST_PLUGIN_PATH=/usr/local/lib/gstreamer-1.0
If you have installed pocketsphinx under a different prefix, you will also need to set the LD_LIBRARY_PATH variable. If your installation prefix is $psprefix, then you would want to set these variables.

export LD_LIBRARY_PATH=$psprefix/lib
export GST_PLUGIN_PATH=$psprefix/lib/gstreamer-1.0
```

