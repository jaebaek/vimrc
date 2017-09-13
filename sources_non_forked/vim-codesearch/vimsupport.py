# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from __future__ import absolute_import

import os
import sys
import vim

try:
  from urllib.error import URLError, HTTPError
except ImportError:
  from urllib2 import URLError, HTTPError

sys.path.append(os.path.join(CR_CS_PYTHON_ROOT, 'third_party', 'codesearch-py'))
sys.path.append(CR_CS_PYTHON_ROOT)

try:
  from codesearch import CodeSearch, CompoundRequest, SearchRequest, \
          XrefSearchRequest, CallGraphRequest, EdgeEnumKind, XrefSearchResponse, \
          AnnotationType, AnnotationTypeValue, NoSourceRootError, \
          InstallTestRequestHandler
  from render.render import RenderCompoundResponse, RenderNode, LocationMapper, DisableConcealableMarkup
except ImportError:
  vim.command('echoerr "{}"'.format(r"""Can't import 'codesearch' module.

Looks like the 'codesearch-py' module can't be located. This is pulled into the
vim-codesearch plugin via Git Submodules. In case your package manager didn't
pull in the submodule, could you try the following?

    cd {:s}
    git submodule update --init --recursive
""".format(CR_CS_PYTHON_ROOT).replace('\n', r'\n')))
  quit()

g_codesearch = None

g_buffer_map_ = {}


def CalledFromVim(default=None):

  def wrapper(func):

    def inner_call_wrapper(*args, **kwargs):
      global g_codesearch
      try:
        return func(*args, **kwargs)
      except (URLError, HTTPError):
        vim.command(
            'echoerr "{}"'.format('couldn\'t contact codesearch server.'))
        return default
      except NoSourceRootError:
        vim.command('echoerr "{}"'.format(
            r"""Couldn't determine Chromium source location.

In order to show search results and link to corresponding files in the working
directory, this plugin needs to know the location of your Chromium checkout.
This can be accomplished via two ways:

  1) Invoke :CrSearch or a similar command while editing a file inside the
     Chromium source directory.

  2) Set g:codesearch_source_root to the directory above your 'src' directory.
     I.e. this should point to the directory containing your .gclient file.
     This can be done by adding something like the following to your .vimrc:

         \" Change this to point to the directory above your Chromium checkout.
         \" E.g.: If you checked out Chromium to ~/sources/chrome/src
         let g:codesearch_source_root = '~/sources/chrome/'
""".replace('\n', r'\n')))
        g_codesearch = None
        return default

    return inner_call_wrapper

  return wrapper


def _GetCodeSearch(base_filename=None):
  global g_codesearch
  if g_codesearch:
    return g_codesearch

  arguments = {'user_agent_string': 'Vim-CodeSearch-Client'}

  if 'codesearch_source_root' in vim.vars:
    arguments['source_root'] = vim.vars['codesearch_source_root']
  else:
    if not base_filename:
      base_filename = vim.eval("expand('%:p')")

    if not base_filename:
      base_filename = vim.eval('getcwd()')

    arguments['a_path_inside_source_dir'] = base_filename

  if 'codesearch_cache_dir' in vim.vars:
      arguments['cache_dir'] = vim.vars['codesearch_cache_dir']
      arguments['should_cache'] = True

  if 'codesearch_cache_timeout_in_seconds' in vim.vars:
      arguments['cache_timeout_in_seconds'] = int(vim.vars['codesearch_cache_timeout_in_seconds'])

  g_codesearch = CodeSearch(**arguments)

  if 'codesearch_source_root' not in vim.vars:
    vim.vars['codesearch_source_root'] = g_codesearch.GetSourceRoot()

  return g_codesearch


def _SetupVimBuffer(t, name):
  assert g_codesearch

  buffer_num = vim.eval(
      "crcs#SetupCodesearchBuffer('{name}', '{source_root}', '{type}')".format(
          name=name, source_root=_GetCodeSearch().GetSourceRoot(), type=t))
  buffer_num = int(buffer_num)
  g_buffer_map_[buffer_num] = None
  return buffer_num


def _GetLocationMapForCurrentBuffer():
  buffer_num = vim.current.buffer.number
  if buffer_num not in g_buffer_map_:
    vim.command('echo "Buffer #{} not in map"'.format(buffer_num))
    return None
  return g_buffer_map_[buffer_num]


@CalledFromVim()
def CleanupBuffer(buffer_num):
  del g_buffer_map_[buffer_num]


def _GetJumpTargetAtPos():
  location_map = _GetLocationMapForCurrentBuffer()

  _, line, column, _ = vim.eval("getpos('.')")
  line = int(line)
  column = int(column)

  return location_map.JumpTargetAt(line, column)


@CalledFromVim()
def JumpToContext():
  root_path = vim.current.buffer.vars.get('cs_root_path', None)
  if root_path is None or root_path == '':
    return

  target = _GetJumpTargetAtPos()
  if target is None:
    return

  filename, line, col = target
  filename = os.path.join(root_path, filename)
  vim.command('e {}'.format(filename))
  vim.eval("setpos('.', [%d, %d, %d, %d])" % (0, line, col, 0))


@CalledFromVim()
def JumpToNextFile():
  location_map = _GetLocationMapForCurrentBuffer()
  _, line, col, _ = vim.eval("getpos('.')")
  line = int(line)
  col = int(col)
  line = location_map.NextFileLocation(line)
  vim.eval("setpos('.', [%d, %d, %d, %d])" % (0, line, col, 0))
  vim.command('norm zz')


@CalledFromVim()
def JumpToPrevFile():
  location_map = _GetLocationMapForCurrentBuffer()
  _, line, col, _ = vim.eval("getpos('.')")
  line = int(line)
  col = int(col)
  line = location_map.PreviousFileLocation(line)
  vim.eval("setpos('.', [%d, %d, %d, %d])" % (0, line, col, 0))
  vim.command('norm zz')


def _GetSignatureAtSource():
  buffer_num = vim.current.buffer.number
  if buffer_num in g_buffer_map_:
    location_map = g_buffer_map_[buffer_num]
    try:
      signature = location_map.SignatureAt(int(vim.eval("line('.')")))
    except:
      signature = None
    return signature

  _, line, column, _ = vim.eval("getpos('.')")
  line = int(line)
  column = int(column)

  filename = vim.eval("expand('%:p')")
  cs = _GetCodeSearch(filename)

  if cs.IsContentStale(filename, vim.current.buffer[:line], check_prefix=True):
    return cs.GetSignatureForSymbol(filename, vim.eval("expand('<cword>')"))

  return cs.GetSignatureForLocation(filename, line, column)


@CalledFromVim()
def RunCodeSearch(q):
  cs = _GetCodeSearch()
  buffer_num = _SetupVimBuffer('search', 'Codesearch: %s' % (q))
  response = cs.SendRequestToServer(
      CompoundRequest(search_request=[
          SearchRequest(
              query=q,
              return_all_snippets=True,
              return_snippets=True,
              lines_context=3,
              return_decorated_snippets=True)
      ]))

  location_map = RenderCompoundResponse(response)
  g_buffer_map_[buffer_num] = location_map
  vim.command('setlocal modifiable')
  vim.current.buffer[:] = location_map.Lines()
  vim.command('setlocal nomodifiable')


@CalledFromVim()
def RunXrefSearch():
  signature = _GetSignatureAtSource()
  if signature is None:
    return

  buffer_num = _SetupVimBuffer('xref', 'Crossreferences')
  cs = _GetCodeSearch()
  response = cs.SendRequestToServer(
      CompoundRequest(xref_search_request=[
          XrefSearchRequest(
              query=signature, file_spec=cs.GetFileSpec(), max_num_results=100)
      ]))

  location_map = RenderCompoundResponse(response)
  g_buffer_map_[buffer_num] = location_map
  vim.command('setlocal modifiable')
  vim.current.buffer[:] = location_map.Lines()
  vim.command('setlocal nomodifiable')


def _FindNodeForSignature(node, signature):
  if node.signature == signature:
    return node
  if hasattr(node, 'children'):
    for child in node.children:
      n = _FindNodeForSignature(child, signature)
      if n is not None:
        return n
  return None


@CalledFromVim()
def RunCallgraphSearch():
  is_nested_query = (vim.current.buffer.vars.get('cs_buftype', '') == 'call')
  signature = None
  parent_node = None
  root_node = None
  if is_nested_query:
    if vim.current.buffer.number not in g_buffer_map_:
      return

    location_map = g_buffer_map_[vim.current.buffer.number]
    signature = location_map.SignatureAt(int(vim.eval("line('.')")))
    root_node = location_map.root_node
    parent_node = _FindNodeForSignature(root_node, signature)
    assert parent_node is not None
  else:
    signature = _GetSignatureAtSource()

  if signature is None:
    return

  # Children of parent node have already been resolved.
  if parent_node is not None and hasattr(parent_node, 'children'):
    return

  cs = _GetCodeSearch()
  response = cs.SendRequestToServer(
      CompoundRequest(call_graph_request=[
          CallGraphRequest(
              signature=signature,
              file_spec=cs.GetFileSpec(),
              max_num_results=100)
      ]))

  if response is None:
    return

  if parent_node is not None:
    assert root_node is not None

    if not hasattr(response, 'call_graph_response') or \
            not hasattr(response.call_graph_response[0], 'node'):
      # |parent_node| has no children known to the server.
      setattr(parent_node, 'children', [])
    else:
      # |new_node.children| are the new children that we are going to 
      # attach to the parent node.
      new_node = response.call_graph_response[0].node

      assert parent_node.signature == new_node.signature
      if hasattr(new_node, 'children'):
        setattr(parent_node, 'children', new_node.children)
      else:
        setattr(parent_node, 'children', [])
    buffer_num = vim.current.buffer.number

  else:
    root_node = response.call_graph_response[0].node
    buffer_num = _SetupVimBuffer('call', 'Callgraph')

  RenderCallGraphInBuffer(root_node, buffer_num)


def RenderCallGraphInBuffer(root_node, buffer_num):
  location_map = LocationMapper()
  RenderNode(location_map, root_node, 0)
  setattr(location_map, 'root_node', root_node)
  g_buffer_map_[buffer_num] = location_map

  vim.command('setlocal modifiable')
  vim.current.buffer[:] = location_map.Lines()
  vim.command('setlocal nomodifiable')


@CalledFromVim()
def CloseCallgraphFold():
  if vim.current.buffer.number not in g_buffer_map_:
    return

  location_map = g_buffer_map_[vim.current.buffer.number]
  signature = location_map.SignatureAt(int(vim.eval("line('.')")))
  root_node = location_map.root_node
  parent_node = _FindNodeForSignature(root_node, signature)
  assert parent_node is not None

  if not hasattr(parent_node, 'children') or len(parent_node.children) == 0:
    # Nothing to do.
    return

  delattr(parent_node, 'children')

  RenderCallGraphInBuffer(root_node, vim.current.buffer.number)


@CalledFromVim(default='')
def GetCallers():
  signature = _GetSignatureAtSource()
  if signature is None or signature == '':
    return ''

  cs = _GetCodeSearch()
  response = cs.SendRequestToServer(
      CompoundRequest(call_graph_request=[
          CallGraphRequest(
              signature=signature,
              file_spec=cs.GetFileSpec(),
              max_num_results=100)
      ]))
  if response is None or not hasattr(
      response, 'call_graph_response') or not hasattr(
          response.call_graph_response[0], 'node'):
    return ''

  node = response.call_graph_response[0].node
  if not hasattr(node, 'children'):
    return ''

  lines = []
  for c in node.children:
    if not hasattr(c, 'file_path') or not hasattr(c, 'call_site_range'):
      continue
    lines.append('{}:{}:{}: {}'.format(
        os.path.join(cs.GetSourceRoot(), c.file_path), c.call_site_range.
        start_line, c.call_site_range.start_column, c.display_name))
  return '\n'.join(lines)


def _XrefSearchResultsToQuickFixList(cs, results):
  lines = []
  for r in results:
    for m in r.match:
      lines.append('{}:{}:1: {}'.format(
          os.path.join(cs.GetSourceRoot(), r.file.name), m.line_number,
          m.line_text))
  return lines


def _GetLocationsForXrefType(t):
  signature = _GetSignatureAtSource()
  if not signature:
    return []

  cs = _GetCodeSearch()
  results = cs.GetXrefsFor(signature, [t])
  return _XrefSearchResultsToQuickFixList(cs, results)


def _GetCallTargets():
  signature = _GetSignatureAtSource()
  if not signature:
    return []
  cs = _GetCodeSearch()
  results = cs.GetCallTargets(signature)
  return _XrefSearchResultsToQuickFixList(cs, results)


REFERENCE_TYPES = {
    'call': EdgeEnumKind.CALL,
    'called at': EdgeEnumKind.CALLED_AT,
    'caller': EdgeEnumKind.CALLED_AT,
    'declaration': EdgeEnumKind.HAS_DECLARATION,
    'definition': EdgeEnumKind.HAS_DEFINITION,
    'extended by': EdgeEnumKind.EXTENDED_BY,
    'extends': EdgeEnumKind.EXTENDS,
    'instantiations': EdgeEnumKind.INSTANTIATED_AT,
    'overridden by': EdgeEnumKind.OVERRIDDEN_BY,
    'overrides': EdgeEnumKind.OVERRIDES,
    'references': EdgeEnumKind.REFERENCED_AT,
    'subclasses': EdgeEnumKind.EXTENDED_BY,
    'superclasses': EdgeEnumKind.EXTENDS,
    'call targets': _GetCallTargets,
}


@CalledFromVim(default=[])
def ReferenceTypeCompleter(arglead, cmdline, cursorpos):
  if arglead == '':
    return REFERENCE_TYPES.keys()

  candidates = []
  arglead = arglead.lower()
  for k in REFERENCE_TYPES.iterkeys():
    if k.startswith(arglead):
      candidates.append(k)
  return candidates


@CalledFromVim(default=[])
def GetReferences(type_string):
  type_string = type_string.lower()
  if type_string not in REFERENCE_TYPES:
    for s in REFERENCE_TYPES.keys():
      if s.startswith(type_string):
        type_string = s
        break

  if type_string not in REFERENCE_TYPES:
    return []

  resolved_type = REFERENCE_TYPES[type_string]
  if callable(resolved_type):
    return resolved_type()

  return _GetLocationsForXrefType(resolved_type)


@CalledFromVim()
def ShowAnnotationsHere():
  filename = vim.eval("expand('%:p')")
  cs = _GetCodeSearch(filename)
  result = cs.GetAnnotationsForFile(
      filename, [AnnotationType(id=AnnotationTypeValue.XREF_SIGNATURE)])
  result = result.annotation_response[0]
  _, line, column, _ = vim.eval("getpos('.')")
  line = int(line)
  column = int(column)
  for annotation in result.annotation:
    if annotation.range.Contains(line, column):
      vim.command('echo \'{}\''.format('&'.join('{}={}'.format(
          k, v) for k, v in annotation.AsQueryString())))


@CalledFromVim()
def ShowSignature():
  signature = _GetSignatureAtSource()
  if signature is None:
    return

  vim.command('echo \'Signature: {}\''.format(signature))

@CalledFromVim()
def PrepareForTesting():
    InstallTestRequestHandler(test_data_dir=vim.eval('g:codesearch_test_data_dir'))

