"""Convert HTML to PayloadCMS Lexical editor format."""

from html.parser import HTMLParser
from typing import Any, Dict, List


class HTMLToLexicalConverter(HTMLParser):
    """Convert HTML to Lexical JSON structure."""
    
    def __init__(self):
        super().__init__()
        self.root_children: List[Dict[str, Any]] = []
        self.current_stack: List[Dict[str, Any]] = []
        self.text_buffer = ""
        
        # Map HTML tags to Lexical node types
        self.block_tags = {
            'p': 'paragraph',
            'h1': 'heading',
            'h2': 'heading',
            'h3': 'heading',
            'h4': 'heading',
            'h5': 'heading',
            'h6': 'heading',
            'blockquote': 'quote',
            'li': 'listitem',
        }
        
        self.list_tags = {'ul': 'bullet', 'ol': 'number'}
        self.inline_tags = {'strong', 'b', 'em', 'i', 'code', 'a', 'span'}
        # Container tags that should be ignored but their content processed
        self.container_tags = {'div', 'section', 'article', 'main', 'aside', 'nav', 'header', 'footer'}
        # Tags to completely ignore (including their content)
        self.ignore_tags = {'script', 'style', 'iframe'}
        self.ignoring_depth = 0  # Track depth when ignoring tags
        self.current_formats: List[str] = []
        self.current_link: str | None = None
        
    def handle_starttag(self, tag, attrs):
        """Handle opening tags."""
        # If we're ignoring content, track depth
        if self.ignoring_depth > 0:
            self.ignoring_depth += 1
            return
        
        # Start ignoring if this is an ignore tag
        if tag in self.ignore_tags:
            self.ignoring_depth = 1
            return
        
        # Flush any pending text
        self._flush_text()
        
        # Skip container tags - just process their content
        if tag in self.container_tags:
            return
        
        if tag in self.block_tags:
            node = self._create_block_node(tag, attrs)
            if self.current_stack:
                # We're inside another block (like a list)
                parent = self.current_stack[-1]
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(node)
            else:
                self.root_children.append(node)
            self.current_stack.append(node)
            
        elif tag in self.list_tags:
            node = self._create_list_node(tag)
            if self.current_stack:
                parent = self.current_stack[-1]
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(node)
            else:
                self.root_children.append(node)
            self.current_stack.append(node)
            
        elif tag in ('strong', 'b'):
            self.current_formats.append('bold')
        elif tag in ('em', 'i'):
            self.current_formats.append('italic')
        elif tag == 'code':
            self.current_formats.append('code')
        elif tag == 'a':
            # Handle links
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    self.current_link = attr_value
                    break
    
    def handle_endtag(self, tag):
        """Handle closing tags."""
        # If we're ignoring, decrease depth
        if self.ignoring_depth > 0:
            self.ignoring_depth -= 1
            return
        
        # Flush any pending text
        self._flush_text()
        
        # Skip container tags
        if tag in self.container_tags:
            return
        
        if tag in self.block_tags or tag in self.list_tags:
            if self.current_stack:
                self.current_stack.pop()
        elif tag in ('strong', 'b'):
            if 'bold' in self.current_formats:
                self.current_formats.remove('bold')
        elif tag in ('em', 'i'):
            if 'italic' in self.current_formats:
                self.current_formats.remove('italic')
        elif tag == 'code':
            if 'code' in self.current_formats:
                self.current_formats.remove('code')
        elif tag == 'a':
            self.current_link = None
    
    def handle_data(self, data):
        """Handle text content."""
        # Skip if we're ignoring content
        if self.ignoring_depth > 0:
            return
        
        # Strip leading/trailing whitespace but preserve meaningful spaces
        if data.strip():
            self.text_buffer += data
    
    def _flush_text(self):
        """Add accumulated text to the current node."""
        if not self.text_buffer:
            return
        
        text = self.text_buffer.strip()
        if not text:
            self.text_buffer = ""
            return
        
        # Create text node
        text_node = self._create_text_node(text)
        
        # Add to current block's children
        if self.current_stack:
            parent = self.current_stack[-1]
            if 'children' not in parent:
                parent['children'] = []
            parent['children'].append(text_node)
        else:
            # Text without a parent block, wrap in paragraph
            para = self._create_block_node('p', [])
            para['children'] = [text_node]
            self.root_children.append(para)
        
        self.text_buffer = ""
    
    def _create_block_node(self, tag: str, attrs: List) -> Dict[str, Any]:
        """Create a block-level Lexical node."""
        node_type = self.block_tags.get(tag, 'paragraph')
        
        node: Dict[str, Any] = {
            "type": node_type,
            "format": "",
            "indent": 0,
            "version": 1,
            "children": [],
            "direction": "ltr"
        }
        
        # Add heading tag for h1-h6
        if tag.startswith('h'):
            node["tag"] = tag
        
        return node
    
    def _create_list_node(self, tag: str) -> Dict[str, Any]:
        """Create a list Lexical node."""
        list_type = self.list_tags[tag]
        return {
            "type": "list",
            "listType": list_type,
            "start": 1,
            "tag": tag,
            "format": "",
            "indent": 0,
            "version": 1,
            "children": [],
            "direction": "ltr"
        }
    
    def _create_text_node(self, text: str) -> Dict[str, Any]:
        """Create a text Lexical node."""
        # Calculate format flags (bit flags)
        format_value = 0
        if 'bold' in self.current_formats:
            format_value |= 1  # Bold = 1
        if 'italic' in self.current_formats:
            format_value |= 2  # Italic = 2
        if 'code' in self.current_formats:
            format_value |= 16  # Code = 16
        
        node: Dict[str, Any] = {
            "mode": "normal",
            "text": text,
            "type": "text",
            "style": "",
            "detail": 0,
            "format": format_value,
            "version": 1
        }
        
        # Handle links
        if self.current_link:
            node["type"] = "link"
            node["fields"] = {
                "linkType": "custom",
                "url": self.current_link
            }
        
        return node
    
    def _clean_empty_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove nodes with empty children arrays."""
        cleaned = []
        for node in nodes:
            # Recursively clean children if they exist
            if 'children' in node:
                node['children'] = self._clean_empty_nodes(node['children'])
                # Keep nodes that have children or are text nodes
                if node['children'] or node.get('type') == 'text':
                    cleaned.append(node)
            else:
                # Keep nodes without children property (like text nodes)
                cleaned.append(node)
        return cleaned
    
    def get_lexical_structure(self) -> Dict[str, Any]:
        """Get the complete Lexical structure."""
        # Flush any remaining text
        self._flush_text()
        
        # Clean up empty nodes
        cleaned_children = self._clean_empty_nodes(self.root_children)
        
        return {
            "root": {
                "type": "root",
                "format": "",
                "indent": 0,
                "version": 1,
                "children": cleaned_children,
                "direction": "ltr"
            }
        }


def html_to_lexical(html: str) -> Dict[str, Any]:
    """Convert HTML string to Lexical editor format.
    
    Parameters
    ----------
    html : str
        HTML content to convert
    
    Returns
    -------
    dict
        Lexical editor JSON structure
    """
    converter = HTMLToLexicalConverter()
    converter.feed(html)
    return converter.get_lexical_structure()

