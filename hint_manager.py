from __future__ import annotations
from typing import List, Optional, Tuple


def generate_tags(n: int, chars: str) -> List[str]:
    """Generate n unique prefix-free tags using chars in priority order."""
    if n == 0:
        return []
    if len(chars) <= 1:
        return [chars * (i + 1) for i in range(n)]

    tags = list(chars)
    char_to_idx = {c: i for i, c in enumerate(chars)}
    
    while len(tags) < n:
        # To maintain prefix-free property while keeping tags for high-priority items short,
        # expand the node that has the minimum length, and among those, the lowest priority (highest index).
        min_len = min(len(t) for t in tags)
        candidates = [t for t in tags if len(t) == min_len]
        to_expand = max(candidates, key=lambda t: [char_to_idx[c] for c in t])
        
        tags.remove(to_expand)
        for c in chars:
            tags.append(to_expand + c)
            
    tags.sort(key=lambda t: (len(t), [char_to_idx[c] for c in t]))
    return tags[:n]



class HintState:
    CLICK_LEFT = 'left'
    CLICK_RIGHT = 'right'
    CLICK_DOUBLE = 'double'
    CLICK_MIDDLE = 'middle'

    def __init__(self, elements: List[Tuple], tags: List[str]) -> None:
        # elements[i] = (BoundingRectangle, UIA control)
        self.elements = elements
        self.tags = tags
        self.click_mode = self.CLICK_LEFT
        self.typed = ''
        self.visible: set = set(range(len(elements)))

    def input_char(self, char: str) -> str:
        """
        Returns 'invalid', 'filter', or 'match'.
        On 'match', call get_match() to retrieve the element.
        """
        new_typed = self.typed + char
        matching = [i for i in self.visible if self.tags[i].startswith(new_typed)]
        if not matching:
            return 'invalid'
        self.typed = new_typed
        self.visible = set(matching)
        if any(self.tags[i] == new_typed for i in matching):
            return 'match'
        return 'filter'

    def backspace(self) -> None:
        if not self.typed:
            return
        self.typed = self.typed[:-1]
        if self.typed:
            self.visible = {i for i in range(len(self.elements))
                            if self.tags[i].startswith(self.typed)}
        else:
            self.visible = set(range(len(self.elements)))

    def get_match(self) -> Optional[Tuple]:
        """Return the (rect, element) for the exactly-matched tag."""
        for i in self.visible:
            if self.tags[i] == self.typed:
                return self.elements[i]
        return None

    def set_click_mode(self, mode: str) -> None:
        self.click_mode = mode
