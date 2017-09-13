Chromium CodeSearch Library
===========================

The `codesearch` Python library provides an interface for talking to the
Chromium CodeSearch backend at https://cs.chromium.org/

The primary entry point into the library is the `CodeSearch` class. Various
message classes you are likely to encounter are defined in `messages.py`.

A quick example:

``` python
'''

Step 1 is to import codesearch.
>>> import codesearch

The following examples are written out as Python doctests and are run as a part
of the run_tests.sh suite. The InstallTestRequestHandler() sets up a test rig
that is used during testing to ensure that tests are reproducible and can be run
without a network connection. Feel free to use InstallTestRequestHandler() in
your own code if you need to test against the CodeSearch library. See
documentation for details.
>>> codesearch.InstallTestRequestHandler()

The plugin can optionally work with a local Chromium checkout (see the
documentation for CodeSearch.__init__()), but for this example, we are going use
the API without a local checkout. This is indicated by setting the |source_root|
to '.'.
>>> cs = codesearch.CodeSearch(source_root='.')

Let's look up a class:
The SearchForSymbol function searches for a symbol of a specific type. In this
case we are looking for a class named File. There may be more than one such
class, so the function returns an array. We only need the first one.
>>> file_class = cs.SearchForSymbol('File', codesearch.NodeEnumKind.CLASS)[0]

SearchForSymbol returns an XrefNode object. This is a starting point for cross
reference lookups.
>>> isinstance(file_class, codesearch.XrefNode)
True

Say we want to look at all the declared members of the File class. This includes
both member functions and member variables:
>>> members = file_class.GetEdges(codesearch.EdgeEnumKind.DECLARES)

There'll be a bunch of these.
>>> len(members) > 0
True

..  and they are all XrefNode objects.
>>> isinstance(members[0], codesearch.XrefNode)
True

We can find out what kind it is. The kinds that are known to CodeSearch are
described in the codesearch.NodeEnumKind enumeration.
>>> print(members[0].GetXrefKind())
700

Convert between values and symbols using the class member functions ToSymbol(),
and FromSymbol().
>>> print(codesearch.NodeEnumKind.ToSymbol(members[0].GetXrefKind()))
ENUM

In addition to the above, there are lower level APIs to talk to the unofficial
endpoints in the https://cs.chromium.org backend. One such API is
SendRequestToServer.

SendRequestToServer takes a CompoundRequest object ...
>>> response = cs.SendRequestToServer(codesearch.CompoundRequest(
...     search_request=[
...     codesearch.SearchRequest(query='hello world',
...                              return_line_matches=True,
...                              lines_context=0)
...     ]))

.. and returns a CompoundResponse
>>> isinstance(response, codesearch.CompoundResponse)
True

Both CompoundRequest and CompoundResponse are explained in
codesearch/messages.py. Since our request was a |search_request| which is a list
of SearchRequest objects, our CompoundResponse object is going to have a
|search_response| field ...
>>> hasattr(response, 'search_response')
True

.. containing a list of SearchResponse objects ...
>>> isinstance(response.search_response, list)
True

.. which contains exactly one element ...
>>> len(response.search_response)
1

.. whose type is SearchResponse.
>>> isinstance(response.search_response[0], codesearch.SearchResponse)
True

It should indicate an estimate of how many results exist. This could diverge
from the number of results included in this response message. If that's the
case, then |hit_max_results| would be true.
>>> response.search_response[0].hit_max_results
True

We can now examine the SearchResult objects to see what the server sent us. The
fields are explained in message.py.
>>> lines_left = 10
>>> for search_result in response.search_response[0].search_result:
...     assert isinstance(search_result, codesearch.SearchResult)
... 
...     for match in search_result.match:
...         print("{}:{}: {}".format(search_result.top_file.file.name,
...                                  match.line_number,
...                                  match.line_text.strip()))
...         lines_left -= 1
...         if lines_left == 0: break
...     if lines_left == 0: break
src/gin/shell/hello_world.js:6: console.log("Hello World");
src/tools/gn/tutorial/hello_world.cc:8: printf("Hello, world.\n");
src/native_client/tests/hello_world/at_exit.c:10: void hello_world(void) {
src/native_client/tests/hello_world/at_exit.c:11: printf("Hello, World!\n");
src/native_client/tests/hello_world/at_exit.c:17: atexit(hello_world);
tools/depot_tools/third_party/boto/pyami/helloworld.py:24: class HelloWorld(ScriptBase):
tools/depot_tools/third_party/boto/pyami/helloworld.py:27: self.log('Hello World!!!')
src/third_party/skia/example/HelloWorld.cpp:37: HelloWorldWindow::~HelloWorldWindow() {
src/third_party/skia/example/HelloWorld.cpp:124: static const char message[] = "Hello World";
src/third_party/skia/example/HelloWorld.cpp:54: SkString title("Hello World ");

Note that in the example above:
*  search_result.match was available because |return_line_matches| was set to
   True when making the server request. Otherwise the server response will not
   contain line matches.
*  The line matches will have multiple lines of context. This was suppressed in
   the example by setting |lines_context| to 0.
'''
```

In addition, the library also includes facilities for maintaining an ephemeral
or persistent cache in order to minimize generated network traffic.

**Note**: The library uses an unsupported interface to talk to the backend. If
you are using the library and it suddenly stops working, file an issue and/or
monitor the project on GitHub for updates.

**Note**: This is not an official Google product.

Support
-------

Feel free to submit issues on GitHub and/or contact the authors. This project is
not officially supported by Google or the Chromium project.

Contributing
------------

See [CONTRIBUTING](./CONTRIBUTING.md) for details on contributing.

