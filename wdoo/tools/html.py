import re
import logging
import collections

import markupsafe
from lxml import etree
from lxml.html import clean

from wdoo.loglevels import ustr
from wdoo.tools import misc

_logger = logging.getLogger(__name__)

allowed_tags = clean.defs.tags | frozenset('article bdi section header footer hgroup nav aside figure main'.split() + [etree.Comment])
tags_to_kill = ['base', 'embed', 'frame', 'head', 'iframe', 'link', 'meta',
                'noscript', 'object', 'script', 'style', 'title']

tags_to_remove = ['html', 'body']
safe_attrs = clean.defs.safe_attrs | frozenset(
    ['style',
     'data-o-mail-quote',  # quote detection
     'data-oe-model', 'data-oe-id', 'data-oe-field', 'data-oe-type', 'data-oe-expression', 'data-oe-translation-id', 'data-oe-nodeid',
     'data-publish', 'data-id', 'data-res_id', 'data-interval', 'data-member_id', 'data-scroll-background-ratio', 'data-view-id',
     'data-class', 'data-mimetype', 'data-original-src', 'data-original-id', 'data-gl-filter', 'data-quality', 'data-resize-width',
     'data-shape', 'data-shape-colors', 'data-file-name', 'data-original-mimetype',
     ])


class _Cleaner(clean.Cleaner):

    _style_re = re.compile(r'''([\w-]+)\s*:\s*((?:[^;"']|"[^";]*"|'[^';]*')+)''')

    _style_whitelist = [
        'font-size', 'font-family', 'font-weight', 'background-color', 'color', 'text-align',
        'line-height', 'letter-spacing', 'text-transform', 'text-decoration', 'opacity',
        'float', 'vertical-align', 'display',
        'padding', 'padding-top', 'padding-left', 'padding-bottom', 'padding-right',
        'margin', 'margin-top', 'margin-left', 'margin-bottom', 'margin-right',
        'white-space',
        # box model
        'border', 'border-color', 'border-radius', 'border-style', 'border-width', 'border-top', 'border-bottom',
        'height', 'width', 'max-width', 'min-width', 'min-height',
        # tables
        'border-collapse', 'border-spacing', 'caption-side', 'empty-cells', 'table-layout']

    _style_whitelist.extend(
        ['border-%s-%s' % (position, attribute)
            for position in ['top', 'bottom', 'left', 'right']
            for attribute in ('style', 'color', 'width', 'left-radius', 'right-radius')]
    )

    strip_classes = False
    sanitize_style = False

    def __call__(self, doc):
        # perform quote detection before cleaning and class removal
        for el in doc.iter(tag=etree.Element):
            self.tag_quote(el)

        super(_Cleaner, self).__call__(doc)

        # if we keep attributes but still remove classes
        if not getattr(self, 'safe_attrs_only', False) and self.strip_classes:
            for el in doc.iter(tag=etree.Element):
                self.strip_class(el)

        # if we keep style attribute, sanitize them
        if not self.style and self.sanitize_style:
            for el in doc.iter(tag=etree.Element):
                self.parse_style(el)

    def tag_quote(self, el):
        def _create_new_node(tag, text, tail=None, attrs=None):
            new_node = etree.Element(tag)
            new_node.text = text
            new_node.tail = tail
            if attrs:
                for key, val in attrs.items():
                    new_node.set(key, val)
            return new_node

        def _tag_matching_regex_in_text(regex, node, tag='span', attrs=None):
            text = node.text or ''
            if not re.search(regex, text):
                return

            child_node = None
            idx, node_idx = 0, 0
            for item in re.finditer(regex, text):
                new_node = _create_new_node(tag, text[item.start():item.end()], None, attrs)
                if child_node is None:
                    node.text = text[idx:item.start()]
                    new_node.tail = text[item.end():]
                    node.insert(node_idx, new_node)
                else:
                    child_node.tail = text[idx:item.start()]
                    new_node.tail = text[item.end():]
                    node.insert(node_idx, new_node)
                child_node = new_node
                idx = item.end()
                node_idx = node_idx + 1

        el_class = el.get('class', '') or ''
        el_id = el.get('id', '') or ''

        # gmail or yahoo // # outlook, html // # msoffice
        if 'gmail_extra' in el_class or \
                'divRplyFwdMsg' in el_id or \
                ('SkyDrivePlaceholder' in el_class or 'SkyDrivePlaceholder' in el_class):
            el.set('data-o-mail-quote', '1')
            if el.getparent() is not None:
                el.getparent().set('data-o-mail-quote-container', '1')

        if (el.tag == 'hr' and ('stopSpelling' in el_class or 'stopSpelling' in el_id)) or \
           'yahoo_quoted' in el_class:
            # Quote all elements after this one
            el.set('data-o-mail-quote', '1')
            for sibling in el.itersiblings(preceding=False):
                sibling.set('data-o-mail-quote', '1')

        # html signature (-- <br />blah)
        signature_begin = re.compile(r"((?:(?:^|\n)[-]{2}[\s]?$))")
        if el.text and el.find('br') is not None and re.search(signature_begin, el.text):
            el.set('data-o-mail-quote', '1')
            if el.getparent() is not None:
                el.getparent().set('data-o-mail-quote-container', '1')

        # text-based quotes (>, >>) and signatures (-- Signature)
        text_complete_regex = re.compile(r"((?:\n[>]+[^\n\r]*)+|(?:(?:^|\n)[-]{2}[\s]?[\r\n]{1,2}[\s\S]+))")
        if not el.get('data-o-mail-quote'):
            _tag_matching_regex_in_text(text_complete_regex, el, 'span', {'data-o-mail-quote': '1'})

        if el.tag == 'blockquote':
            # remove single node
            el.set('data-o-mail-quote-node', '1')
            el.set('data-o-mail-quote', '1')
        if el.getparent() is not None and (el.getparent().get('data-o-mail-quote') or el.getparent().get('data-o-mail-quote-container')) and not el.getparent().get('data-o-mail-quote-node'):
            el.set('data-o-mail-quote', '1')

    def strip_class(self, el):
        if el.attrib.get('class'):
            del el.attrib['class']

    def parse_style(self, el):
        attributes = el.attrib
        styling = attributes.get('style')
        if styling:
            valid_styles = collections.OrderedDict()
            styles = self._style_re.findall(styling)
            for style in styles:
                if style[0].lower() in self._style_whitelist:
                    valid_styles[style[0].lower()] = style[1]
            if valid_styles:
                el.attrib['style'] = '; '.join('%s:%s' % (key, val) for (key, val) in valid_styles.items())
            else:
                del el.attrib['style']


def html_sanitize(src, silent=True, sanitize_tags=True, sanitize_attributes=False, sanitize_style=False, sanitize_form=True, strip_style=False, strip_classes=False):
    if not src:
        return src
    src = ustr(src, errors='replace')
    # html: remove encoding attribute inside tags
    doctype = re.compile(r'(<[^>]*\s)(encoding=(["\'][^"\']*?["\']|[^\s\n\r>]+)(\s[^>]*|/)?>)', re.IGNORECASE | re.DOTALL)
    src = doctype.sub(u"", src)

    logger = logging.getLogger(__name__ + '.html_sanitize')

    # html encode mako tags <% ... %> to decode them later and keep them alive, otherwise they are stripped by the cleaner
    src = src.replace(u'<%', misc.html_escape(u'<%'))
    src = src.replace(u'%>', misc.html_escape(u'%>'))

    kwargs = {
        'page_structure': True,
        'style': strip_style,              # True = remove style tags/attrs
        'sanitize_style': sanitize_style,  # True = sanitize styling
        'forms': sanitize_form,            # True = remove form tags
        'remove_unknown_tags': False,
        'comments': False,
        'processing_instructions': False
    }
    if sanitize_tags:
        kwargs['allow_tags'] = allowed_tags
        if etree.LXML_VERSION >= (2, 3, 1):
            # kill_tags attribute has been added in version 2.3.1
            kwargs.update({
                'kill_tags': tags_to_kill,
                'remove_tags': tags_to_remove,
            })
        else:
            kwargs['remove_tags'] = tags_to_kill + tags_to_remove

    if sanitize_attributes and etree.LXML_VERSION >= (3, 1, 0):  # lxml < 3.1.0 does not allow to specify safe_attrs. We keep all attributes in order to keep "style"
        if strip_classes:
            current_safe_attrs = safe_attrs - frozenset(['class'])
        else:
            current_safe_attrs = safe_attrs
        kwargs.update({
            'safe_attrs_only': True,
            'safe_attrs': current_safe_attrs,
        })
    else:
        kwargs.update({
            'safe_attrs_only': False,  # keep oe-data attributes + style
            'strip_classes': strip_classes,  # remove classes, even when keeping other attributes
        })

    try:
        # some corner cases make the parser crash (such as <SCRIPT/XSS SRC=\"http://ha.ckers.org/xss.js\"></SCRIPT> in test_mail)
        cleaner = _Cleaner(**kwargs)
        cleaned = cleaner.clean_html(src)
        assert isinstance(cleaned, str)
        # MAKO compatibility: $, { and } inside quotes are escaped, preventing correct mako execution
        cleaned = cleaned.replace(u'%24', u'$')
        cleaned = cleaned.replace(u'%7B', u'{')
        cleaned = cleaned.replace(u'%7D', u'}')
        cleaned = cleaned.replace(u'%20', u' ')
        cleaned = cleaned.replace(u'%5B', u'[')
        cleaned = cleaned.replace(u'%5D', u']')
        cleaned = cleaned.replace(u'%7C', u'|')
        cleaned = cleaned.replace(u'&lt;%', u'<%')
        cleaned = cleaned.replace(u'%&gt;', u'%>')
        # html considerations so real html content match database value
        cleaned.replace(u'\xa0', u'&nbsp;')
    except etree.ParserError as e:
        if 'empty' in str(e):
            return u""
        if not silent:
            raise
        logger.warning(u'ParserError obtained when sanitizing %r', src, exc_info=True)
        cleaned = u'<p>ParserError when sanitizing</p>'
    except Exception:
        if not silent:
            raise
        logger.warning(u'unknown error obtained when sanitizing %r', src, exc_info=True)
        cleaned = u'<p>Unknown error when sanitizing</p>'

    # this is ugly, but lxml/etree tostring want to put everything in a 'div' that breaks the editor -> remove that
    if cleaned.startswith(u'<div>') and cleaned.endswith(u'</div>'):
        cleaned = cleaned[5:-6]

    return markupsafe.Markup(cleaned)